"""调度内核：与调度模型无关的簿记与正确性逻辑.

五类逻辑 MUST 由本内核承担，新增调度模型 MUST NOT 重新实现它们：

1. **单一结算收口**（``settle``）——注销在飞状态并在成功时上报结果。不同并发原语
   共用同一条收口路径，因此结果在任一原语下都会被投递。
2. **超时观测与熔断**（``reap_timeout``）——只记录、标记不健康、停止派发。
   CPython 无法安全中断正在执行的线程，故 MUST NOT 声称已终止。
3. **停机资源回收**（``shutdown`` 路径）——停止派发、清空在飞表；容器（如线程池）
   的回收由模型经 ``teardown`` 提供。
4. **运行期注册**（``add_worker``）——调度列表由本内核持有；仅在注册表登记不足以
   让 Worker 被派发。
5. **周期排期判断**（``is_due`` / ``jitter`` / ``skipped_count``）——周期与相位是
   **每个 Worker** 的声明，与并发原语无关；若由各模型自行实现，绝对序列、跳过语义
   与抖动采集会被实现多遍且必然分歧。

另持有模型无关的**并发契约**：在飞表与熔断集合由**单一** ``threading.RLock``
保护（两者会被派发线程与完成回调并发访问），以及运行期指标计数。

时间基准：本模块的一切区间量 MUST 用 ``time.monotonic()``，MUST NOT 混入墙钟。
"""

import threading
import time

from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker

from ..run_identity import RunIdentity, current_identity

#: 抖动的"不适用"标注。未声明周期的 Worker 无周期触发，MUST NOT 以 0 代替——
#: 0 会被误读为"观测到零抖动"。
JITTER_NOT_APPLICABLE = "不适用"

#: 策略缓存的未命中哨兵（#47 P1）。MUST NOT 用 None 兼任——None 本身是合法的
#: 解析结果（"未声明周期"），falsy 值（0 / False / ""）同样是有效配置值，
#: 缓存判据 MUST 是身份比较而非真值判断。
_POLICY_MISS = object()


class WorkerDispatchCore:
    """调度内核.

    Attributes:
        workers: 参与调度的 Worker 列表
        worker_props: 在飞表，worker 名 -> {worker, run_time, run_timeout, deadline, container}
        broken: 已熔断（超时）的 worker 名集合
        stopped: 停机标记
        default_run_timeout: 全局默认超时；``<= 0`` 表示不启用超时判定
    """

    def __init__(self, default_run_timeout=None):
        self.workers: list = []
        self.worker_props: dict = {}
        # 在飞表与熔断集合会被派发线程与完成回调并发访问
        self._lock = threading.RLock()
        self.broken: set = set()
        self.stopped = False
        self.default_run_timeout = default_run_timeout

        # 运行期指标（模型经 metrics() 暴露，MUST NOT 只在停机时可得）
        self._completed = 0
        self._timeouts = 0

        # 周期排期状态（每个 Worker 独立）
        self._period_base: float | None = None
        self._ticks: dict[str, int] = {}
        self._next_at: dict[str, float] = {}
        self._skipped: dict[str, int] = {}
        # 抖动只保留摘要（最近 / 上界 / 样本数），避免长跑 Worker 无限积累样本
        self._jitter: dict[str, dict] = {}

        # 策略解析缓存（#47 P1）：worker 名 -> 属性键 -> 已解析值。此前每轮每个
        # Worker 都重走"自报→覆盖→默认"三段并现拼参数字符串键（实测 9.4 µs/任务，
        # 占提交侧 33%）；解析结果在 Worker 存续期内是静态的（配置无运行期重载），
        # 失效入口只有 set_workers / add_worker(同名) / clear 三处。
        self._policy_cache: dict[tuple[str, str], object] = {}

    # ---------------------------------------------------------------- 调度列表

    def set_workers(self, worker_list) -> None:
        """设置参与调度的 Worker 列表."""
        with self._lock:
            self.workers = list(worker_list)
            # 调度列表整体替换：旧列表的策略条目全部作废
            self._policy_cache.clear()

    def add_worker(self, worker) -> None:
        """把运行期新增的 Worker 纳入调度.

        调度列表由本内核持有，仅在注册表登记不足以让 Worker 被派发。
        """
        if worker is None:
            return
        with self._lock:
            # 同名重注册（如 Master.register_worker 覆盖旧实例）时旧解析作废；
            # 新名字无需动作——缓存惰性填充。
            self._invalidate_policy(worker.name)
            if worker not in self.workers:
                self.workers.append(worker)

    def retain_looping(self, workers) -> list:
        """筛选出本轮结束后仍留在调度列表中的 Worker.

        条件是三项同时成立：非空、**未熔断**、声明循环。熔断的 Worker 必须被移出
        列表，否则它会在下一轮被反复判定（且会让"熔断即停止派发"的语义失效）。
        单次 Worker 不参与下一轮——"恰好执行一次"的语义由本方法与 ``is_inflight``
        共同保证。
        """
        with self._lock:
            return [
                worker
                for worker in workers
                if worker is not None and worker.name not in self.broken and worker.is_loop
            ]

    # ---------------------------------------------------------------- 状态查询

    def is_inflight(self, worker) -> bool:
        with self._lock:
            return worker.name in self.worker_props

    def is_broken(self, worker) -> bool:
        with self._lock:
            return worker.name in self.broken

    # ---------------------------------------------------------------- 周期排期

    def _policy(self, worker, key: str, compute):
        """按 (worker 名, 属性) 缓存一段解析（#47 P1）.

        命中判据是哨兵身份比较：缓存里的 None / 0 / False / "" 都是**有效结果**，
        MUST NOT 被当作未命中重新解析或穿透到默认值。调用方可能已持有
        ``self._lock``（RLock 可重入），这里统一持锁读写。
        """
        cache_key = (worker.name, key)
        with self._lock:
            cached = self._policy_cache.get(cache_key, _POLICY_MISS)
            if cached is not _POLICY_MISS:
                return cached
            value = compute(worker)
            self._policy_cache[cache_key] = value
            return value

    def _invalidate_policy(self, worker_name: str) -> None:
        """作废某个 Worker 名的全部策略条目（调用方已持锁）."""
        stale = [k for k in self._policy_cache if k[0] == worker_name]
        for k in stale:
            del self._policy_cache[k]

    def resolve_period(self, worker):
        """解析 Worker 的周期：自报 → 按 Worker 名覆盖 → 全局默认.

        结果按 Worker 名缓存（#47 P1），三段语义逐项保持：
        falsy 的自报/覆盖值（0 / False / ""）仍按现有规则落到下一段，
        缓存 MUST NOT 改变这一点。

        Returns:
            周期秒数；未声明时返回 None（调用方据此按事件驱动处理）
        """
        return self._policy(worker, "period", self._compute_period)

    @staticmethod
    def _compute_period(worker):
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.params import WorkerParams

        period = getattr(worker, "period", None)
        if period:
            return period

        override = ParamsFactory().get_params(
            f"{WorkerParams.WORKER_OVERRIDE_PREFIX}:{worker.name}:period",
            default_value=None,
        )
        if override:
            return override

        return WorkerParams.WORKER_PERIOD or None

    def resolve_phase(self, worker):
        """解析 Worker 的相位偏移：自报 → 按 Worker 名覆盖 → 全局默认.

        结果按 Worker 名缓存（#47 P1）。相位是典型 falsy 场景：配置里显式
        ``phase: 0`` 是有效值，缓存判据 MUST 是哨兵比较而不是真值判断。

        Returns:
            相位秒数；未声明时返回 0.0
        """
        return self._policy(worker, "phase", self._compute_phase)

    @staticmethod
    def _compute_phase(worker):
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.params import WorkerParams

        phase = getattr(worker, "phase", None)
        if phase:
            return phase

        override = ParamsFactory().get_params(
            f"{WorkerParams.WORKER_OVERRIDE_PREFIX}:{worker.name}:phase",
            default_value=None,
        )
        if override is not None:
            return override

        return WorkerParams.WORKER_PHASE or 0.0

    def is_due(self, worker, now: float | None = None) -> bool:
        """该 Worker 此刻是否到点.

        周期排期以**单调时钟的绝对序列**计算触发时刻（基准 + 相位 + n×周期），
        MUST NOT 以"上一轮执行结束时刻 + 周期"排期——后者会逐轮累积漂移。

        单轮执行跨越了多个理论触发时刻时**跳过**那些已错过的轮次，只在下一个未来
        时刻再次触发，MUST NOT 补跑（补跑会在持续过载下自我放大）。

        **排期基准**是该 Worker **首次到点判定**所用的时刻（框架没有进程级调度纪元），
        因此首次触发落在「首次判定时刻 + 相位」，后续理论时刻为
        「基准 + 相位 + n×周期」。

        Args:
            worker: 目标 Worker
            now: 当前单调时刻；None 表示取 ``time.monotonic()``（便于测试注入）

        Returns:
            是否到点；未声明周期的 Worker 恒为 True（事件驱动语义）
        """
        period = self.resolve_period(worker)
        if not period or period <= 0:
            return True

        now = time.monotonic() if now is None else now

        with self._lock:
            if self._period_base is None:
                self._period_base = now
            key = worker.name
            phase = self.resolve_phase(worker)
            anchor = self._period_base + phase

            if key not in self._next_at:
                # 首次排期：基准 + 相位
                self._ticks[key] = 0
                self._next_at[key] = anchor

            if now < self._next_at[key]:
                return False

            # 到点：记录抖动（实际 - 理论），再把序列推进到第一个**未来**时刻
            self._record_jitter(key, expected=self._next_at[key], actual=now)

            index = int((now - anchor) // period) + 1
            self._skipped[key] = self._skipped.get(key, 0) + max(0, index - (self._ticks[key] + 1))
            self._ticks[key] = index
            self._next_at[key] = anchor + index * period
            return True

    def _record_jitter(self, key: str, expected: float, actual: float) -> None:
        """记录一次触发的抖动摘要（最近 / 上界 / 样本数）."""
        jitter = actual - expected
        summary = self._jitter.get(key)
        if summary is None:
            self._jitter[key] = {"last": jitter, "upper_bound": jitter, "samples": 1}
            return
        summary["last"] = jitter
        # 上界只升不降：后续更小的抖动 MUST NOT 把它拉低
        summary["upper_bound"] = max(summary["upper_bound"], jitter)
        summary["samples"] += 1

    def skipped_count(self, worker) -> int:
        """该 Worker 累计被跳过的轮次数."""
        with self._lock:
            return self._skipped.get(worker.name, 0)

    def jitter(self, worker) -> dict:
        """该 Worker 的触发抖动摘要.

        未声明周期的 Worker 返回显式的"不适用"标注，MUST NOT 返回 0。
        """
        with self._lock:
            summary = self._jitter.get(worker.name)

        if summary is None:
            return {
                "applicable": False,
                "jitter": JITTER_NOT_APPLICABLE,
                "reason": "该 Worker 未声明周期，无周期触发，抖动不适用",
            }
        return {"applicable": True, **summary}

    # ---------------------------------------------------------------- 派发登记

    def begin(self, worker, timeout, deadline: float | None = None) -> dict | None:
        """登记一个即将派发的 Worker.

        **登记 MUST 先于派发**：若先提交任务再登记，瞬时完成的任务会在登记之前
        触发注销，在在飞表中留下一条永不清除的记录，使该 Worker 此后再不被派发。

        Args:
            worker: 目标 Worker
            timeout: 相对超时秒数
            deadline: 绝对截止期（单调时钟基准）；给出时优先于 ``timeout``

        Returns:
            该 Worker 的登记项；若已在飞表中则返回 None（调用方 MUST NOT 派发）
        """
        handle = {
            "worker": worker,
            "run_time": time.monotonic(),
            "run_timeout": timeout,
            "deadline": deadline,
            "container": None,
            # 运行标识在**登记时**捕获并随登记项一起保存：结算可能发生在别的工作线程，
            # 那里的上下文未必是派发时的上下文，故以显式字段为真相来源
            "identity": current_identity(),
        }
        with self._lock:
            if worker.name in self.worker_props:
                return None
            self.worker_props[worker.name] = handle
        return handle

    def attach_container(self, worker, container) -> None:
        """把承载该 Worker 的容器（线程或 Future）挂到登记项上."""
        with self._lock:
            handle = self.worker_props.get(worker.name)
            if handle is not None:
                handle["container"] = container

    def abort(self, worker) -> None:
        """回滚登记：派发失败时清掉登记项，以便下一轮重试."""
        with self._lock:
            self.worker_props.pop(worker.name, None)

    # ---------------------------------------------------------------- 结算收口

    def settle(self, worker, result=None, error=None) -> None:
        """唯一的完成收口：注销在飞状态，并在成功时上报结果.

        无论执行成功与否都必须注销；上报过程自身抛出的异常 MUST NOT 影响注销。

        结果上的运行标识由本方法从**登记项**盖章（而非读取当前上下文）——结算可能
        发生在工作线程，其上下文未必与派发时相同；登记项里的标识才是真相来源。

        Args:
            worker: 完成执行的 Worker
            result: 执行结果；执行失败时为 None
            error: 执行时抛出的异常；成功时为 None
        """
        with self._lock:
            handle = self.worker_props.pop(worker.name, None)
            self._completed += 1

        identity: RunIdentity | None = handle.get("identity") if handle else None
        if identity is None:
            # 登记项已被熔断清理时退回当前上下文，不编造值
            identity = current_identity()

        if result is not None and identity is not None and hasattr(result, "run_id"):
            result.run_id = identity.run_id
            result.session_id = identity.session_id

        if error is not None:
            LogUtils.error(f"Worker {worker.name} 执行失败: {error}", self.__class__.__name__)
            return

        if result is None:
            return

        try:
            EventReactorManager().dispatch(result.topic, result)
        except Exception as e:
            LogUtils.error(f"Worker {worker.name} 结果上报失败: {e}", self.__class__.__name__)

    def run_and_settle(self, worker) -> None:
        """在工作线程里执行一次并结算.

        这是模型与并发原语无关的执行单元：派发侧 MUST 用
        ``carry_context(core.run_and_settle)`` 包装后再提交，否则工作线程不会继承
        调用方的上下文，运行标识会在派发时静默丢失。

        Args:
            worker: 待执行的 Worker
        """
        try:
            result = self.run_worker(worker)
        except Exception as e:
            self.settle(worker, error=e)
        else:
            self.settle(worker, result=result)

    # ---------------------------------------------------------------- 超时熔断

    def resolve_run_timeout(self, worker):
        """解析 Worker 的超时：自报 → 按 Worker 名覆盖 → 全局默认.

        结果按 Worker 名缓存（#47 P1）；全局默认取自 ``default_run_timeout``，
        它在构造后不再变更（变更需同步作废缓存，当前无这样的运行期入口）。

        Returns:
            超时秒数；未声明时返回 None
        """
        return self._policy(worker, "run_timeout", self._compute_run_timeout)

    def _compute_run_timeout(self, worker):
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.params import WorkerParams

        timeout = worker.run_timeout
        if timeout:
            return timeout

        override = ParamsFactory().get_params(
            f"{WorkerParams.WORKER_OVERRIDE_PREFIX}:{worker.name}:runTimeout",
            default_value=None,
        )
        if override:
            return override

        return self.default_run_timeout or None

    def reap_timeout(self, worker) -> bool:
        """超时判定与熔断.

        只做观测与熔断：记录、标记为不健康、不再派发。MUST NOT 声称已终止仍在
        执行的 Worker —— CPython 无法安全中断一个正在执行的线程。

        两种期限来源二选一：登记时给出的**绝对截止期**优先；否则用相对超时。

        Returns:
            本次是否判定为超时
        """
        with self._lock:
            handle = self.worker_props.get(worker.name)
            if handle is None:
                return False

            now = time.monotonic()
            deadline = handle.get("deadline")
            if deadline is not None:
                if now < deadline:
                    return False
                elapsed = now - handle.get("run_time", now)
                reason = f"已超过派发截止期（截止 {deadline:.3f}，当前 {now:.3f}）"
            else:
                timeout = handle.get("run_timeout")
                if not timeout or timeout <= 0:
                    return False
                elapsed = now - handle.get("run_time", 0)
                if elapsed < timeout:
                    return False
                reason = f"执行已超过 {timeout}s（实际 {elapsed:.3f}s）"

            self.broken.add(worker.name)
            self.worker_props.pop(worker.name, None)
            self._timeouts += 1

        LogUtils.error(
            f"Worker {worker.name} {reason}，标记为不健康并停止派发；"
            "注意：系统不会强制终止仍在执行的 Worker",
            self.__class__.__name__,
        )
        return True

    # ---------------------------------------------------------------- 执行入口

    @staticmethod
    def run_worker(worker):
        """执行一个 Worker.

        Returns:
            WorkerResult；worker 非法时返回 None
        """
        if not isinstance(worker, BaseWorker):
            return None

        return worker.run()

    # ---------------------------------------------------------------- 停机

    def mark_stopped(self) -> bool:
        """置停机标记.

        Returns:
            本次调用是否为首次停机（重复调用返回 False）
        """
        with self._lock:
            already_stopped = self.stopped
            self.stopped = True
        return not already_stopped

    def clear(self) -> None:
        """清空调度列表、在飞表与周期排期状态.

        周期排期一并复位：停机后再启动应当重新建立基准，而不是沿用旧序列。
        """
        with self._lock:
            self.workers = []
            self.worker_props.clear()
            self._policy_cache.clear()
            self._period_base = None
            self._ticks.clear()
            self._next_at.clear()
            self._skipped.clear()
            self._jitter.clear()

    # ---------------------------------------------------------------- 指标

    def metrics(self) -> dict:
        """运行期指标：在飞执行数、累计完成数、超期熔断数.

        MUST 可在运行期查询，MUST NOT 只在停机时可得。抖动是**按 Worker** 的观测，
        经 ``jitter(worker)`` 查询，故不在此聚合返回。
        """
        with self._lock:
            return {
                "inflight": len(self.worker_props),
                "completed": self._completed,
                "timeouts": self._timeouts,
            }
