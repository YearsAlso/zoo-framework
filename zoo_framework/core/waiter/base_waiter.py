"""调度器基类。

设计要点：

- **模型无关的正确性逻辑不在本类内实现**，而是下沉到 ``WorkerDispatchCore``：
  单一结算收口、超时观测与熔断、停机资源回收、运行期注册。
- **并发原语与容器生命周期由调度模型承担**（``SchedulerModel``）。本类只负责
  按配置装配模型、跑调度轮，并把派发与停机委托给模型。
- **登记先于派发**（``core.begin`` 先于 ``model.submit``）。若先提交任务再登记，
  瞬时完成的任务会在登记之前就触发注销，在在飞表中留下一条永不清除的记录，
  使该 Worker 此后再不被派发。
- **超时只做"观测 + 熔断"**。CPython 无法安全中断一个正在执行的线程，
  因此系统不声称已终止超时的 Worker，只记录、标记不健康并停止派发。
- **停机是显式动作**。停止派发、交由模型回收容器、清空在飞表，且可重复调用。
"""

import contextlib

from zoo_framework.constant import WaiterConstant
from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor
from zoo_framework.utils import LogUtils

from .dispatch_core import WorkerDispatchCore
from .scheduler_model import (
    LEGACY_POLICY_TO_BACKPRESSURE,
    SchedulerModel,
    ThreadPerTaskModel,
    ThreadPoolModel,
)


class BaseWaiter:
    """基础的 waiter（调度器）.

    Attributes:
        worker_mode: 生效的调度模型名
        pool_enable: 是否使用资源池（由模型名推导）
        model: 已装配的调度模型
        core: 调度内核
    """

    def __init__(
        self,
        model_name: str | None = None,
        pool_size: int | None = None,
        backpressure_policy: str | None = None,
    ):
        """装配调度器.

        Args:
            model_name: 调度模型名（``worker:mode`` 的取值）；None 表示由配置推导
            pool_size: 资源池尺寸；None 表示取 ``worker:pool:size``
            backpressure_policy: 池尺寸不足时的策略；None 表示由 ``worker:runPolicy`` 推导

        Raises:
            NotImplementedError: 模型名对应的模式尚未实现
            ValueError: 运行策略无法识别
        """
        from zoo_framework.params import WorkerParams

        configured_mode, self.pool_enable = self.get_worker_mode(WorkerParams.WORKER_POOL_ENABLE)
        self.worker_mode = self.validate_worker_mode(model_name) if model_name else configured_mode

        size = WorkerParams.WORKER_POOL_SIZE if pool_size is None else pool_size
        policy = (
            backpressure_policy
            if backpressure_policy is not None
            else self._resolve_backpressure_policy(WorkerParams.WORKER_RUN_POLICY)
        )
        # 显式传入的策略同样要校验：线程模式下该参数对模型无意义，但一个写错的取值
        # 若被静默忽略，配置意图就悄悄失守了——MUST NOT 静默忽略
        self._validate_backpressure_policy(policy)

        self.model: SchedulerModel = self._build_model(self.worker_mode, size, policy)

        # 模型无关的簿记与正确性逻辑全部由内核持有（单一所有者）
        self.core = WorkerDispatchCore(default_run_timeout=WorkerParams.WORKER_RUN_TIMEOUT)

        self.register_handler()

    # ------------------------------------------------------------------ 装配

    @staticmethod
    def _build_model(model_name: str, pool_size: int, backpressure_policy: str) -> SchedulerModel:
        """按模型名装配具体模型."""
        if model_name == WaiterConstant.WORKER_MODE_THREAD_POOL:
            return ThreadPoolModel(pool_size=pool_size, backpressure_policy=backpressure_policy)
        return ThreadPerTaskModel()

    @staticmethod
    def _resolve_backpressure_policy(policy: str) -> str:
        """把 ``worker:runPolicy`` 的历史取值映射为背压策略.

        Raises:
            ValueError: 取值无法识别——MUST NOT 静默降级到某个默认策略
        """
        mapped = LEGACY_POLICY_TO_BACKPRESSURE.get(policy)
        if mapped is None:
            raise ValueError(
                f"无法识别的运行策略 {policy!r}；可选 {list(LEGACY_POLICY_TO_BACKPRESSURE)}"
            )
        return mapped

    @staticmethod
    def _validate_backpressure_policy(policy: str) -> None:
        """校验背压策略取值.

        与配置路径共用同一套合法取值；未知取值 MUST 被明确拒绝并列出可选项，
        MUST NOT 被静默忽略——即使当前模型（如线程派发模型）并不使用该参数。

        Raises:
            ValueError: 取值无法识别
        """
        allowed = sorted(set(LEGACY_POLICY_TO_BACKPRESSURE.values()))
        if policy not in allowed:
            raise ValueError(f"无法识别的背压策略 {policy!r}；可选 {allowed}")

    # ------------------------------------------------------------------ 状态视图
    # 调度列表与在飞表的状态归内核所有；此处只暴露**只读**视图，避免两处各存一份。
    # 变更调度列表请用 call_workers / add_worker——直接赋值会绕过模型的 start，
    # 使 submit 按"未启动即提交"的契约拒绝派发。

    @property
    def workers(self):
        return self.core.workers

    @property
    def worker_props(self):
        return self.core.worker_props

    @property
    def _broken(self):
        return self.core.broken

    # ------------------------------------------------------------------ 模式选择

    @staticmethod
    def validate_worker_mode(mode):
        """校验调度模式是否已实现。

        未实现的模式 MUST 被明确拒绝，MUST NOT 静默按其他模式执行。

        Args:
            mode: 调度模式名

        Returns:
            通过校验的模式名

        Raises:
            NotImplementedError: 该模式尚未实现
        """
        if mode not in WaiterConstant.IMPLEMENTED_WORKER_MODES:
            raise NotImplementedError(
                f"调度模式 {mode!r} 尚未实现；已实现的模式为 "
                f"{list(WaiterConstant.IMPLEMENTED_WORKER_MODES)}"
            )
        return mode

    def get_worker_mode(self, pool_enable):
        """获得worker的模式。

        显式配置的 ``worker:mode`` 优先；未配置时由 ``worker:pool:enable`` 推导。
        未实现的模式会被明确拒绝。

        Args:
            pool_enable: 资源池开关

        Returns:
            (模式名, 是否使用资源池)
        """
        from zoo_framework.params import WorkerParams

        mode = WorkerParams.WORKER_MODE
        if not mode:
            mode = (
                WaiterConstant.WORKER_MODE_THREAD_POOL
                if pool_enable
                else WaiterConstant.WORKER_MODE_THREAD
            )
        self.validate_worker_mode(mode)
        return mode, mode == WaiterConstant.WORKER_MODE_THREAD_POOL

    def register_handler(self):
        """注册handler。

        把结果响应器绑定到统一的结果主题。``bind_topic_reactor`` 具备幂等语义，
        因此重复构造调度器不会在主题下堆积重复的响应器。
        """
        EventReactorManager().bind_topic_reactor(
            WaiterConstant.WORKER_RESULT_TOPIC, WaiterResultReactor()
        )

    # ------------------------------------------------------------------ 集结与注册

    def call_workers(self, worker_list: list):
        """集结worker们，并按背压策略启动模型容器.

        Args:
            worker_list: 参与调度的 Worker 列表
        """
        self.core.set_workers(worker_list)
        # 背压策略必须在建池之前生效：expand 会放宽尺寸，建池后再放宽已无意义
        self.model.prepare_workers(self.core.workers)
        self.model.start(self.core)

    def add_worker(self, worker):
        """把运行期新增的 Worker 纳入调度。

        调度列表由调度器持有，仅在注册表登记不足以让 Worker 被派发。

        Args:
            worker: 待加入调度的 Worker
        """
        self.core.add_worker(worker)

    def __del__(self):
        # 释放阶段不做任何可能抛异常的清理：__del__ 抛出的异常只会打印到 stderr
        with contextlib.suppress(Exception):
            self.shutdown(wait=False)

    # ------------------------------------------------------------------ 调度轮

    def execute_service(self):
        """执行服务。

        本轮结束后仍保留在调度列表中的，只有声明循环且未被熔断的 Worker。
        """
        if self.core.stopped:
            return

        for worker in list(self.core.workers):
            # 非法调度项直接忽略，MUST NOT 因其抛出属性访问异常
            if worker is None:
                continue

            # 超时判定先于在飞判定：判定为超时的 Worker 本轮即被熔断
            self.core.reap_timeout(worker)

            if self.core.is_broken(worker):
                continue

            # 在飞判定先于周期排期：周期排期带副作用（推进序列），若对一个仍在执行的
            # Worker 调用它，会把这次触发"消费掉"却不派发
            if self.core.is_inflight(worker):
                continue

            # 周期排期：未到点的周期 Worker 本轮跳过，但仍留在调度列表中
            if not self.core.is_due(worker):
                continue

            self._dispatch_worker(worker)

        self.core.workers = self.core.retain_looping(self.core.workers)

    def _dispatch_worker(self, worker):
        """派遣 worker。

        登记 MUST 先于派发，否则瞬时完成的任务会在登记之前就完成注销。

        Args:
            worker: 待派发的 Worker
        """
        handle = self.core.begin(worker, self.core.resolve_run_timeout(worker))
        if handle is None:
            return

        try:
            self.model.submit(self.core, worker)
        except Exception as e:
            # 派发失败不得中断整轮调度；清掉登记以便下一轮重试
            self.core.abort(worker)
            LogUtils.error(f"Worker {worker.name} 派发失败: {e}", self.__class__.__name__)

    # ------------------------------------------------------------------ 停机

    def shutdown(self, wait: bool = True, timeout: float | None = None) -> None:
        """停机：停止派发并交由模型回收容器。

        MUST 可重复调用。

        Args:
            wait: 是否等待在飞任务结束
            timeout: 等待上限（秒）；None 表示不设上限
        """
        if not self.core.mark_stopped():
            return

        LogUtils.info("Waiter 停机中", self.__class__.__name__)

        self.model.teardown(self.core, wait=wait, timeout=timeout)
        self.core.clear()
