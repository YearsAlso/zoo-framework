"""调度器基类。

设计要点（对应 fix-worker-scheduling 的 A / B 组）：

- **登记先于派发**。若先提交任务再登记，瞬时完成的任务会在登记之前就触发注销，
  在在飞表中留下一条永不清除的记录，使该 Worker 此后再不被派发。
- **注销与上报由任务完成回调单点收口**。两种调度模式共用同一条收口路径，
  因此线程模式的结果同样会被投递（此前线程模式的结果被直接丢弃）。
- **超时只做"观测 + 熔断"**。CPython 无法安全中断一个正在执行的线程，
  因此系统不声称已终止超时的 Worker，只记录、标记不健康并停止派发。
- **停机是显式动作**。停止派发、回收线程资源、清空在飞表，且可重复调用。
"""

import contextlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from zoo_framework.constant import WaiterConstant
from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker


class BaseWaiter:
    """基础的 waiter（调度器）。"""

    _lock = None

    def __init__(self):
        from zoo_framework.params import WorkerParams

        # 获得模式
        self.worker_mode, self.pool_enable = self.get_worker_mode(WorkerParams.WORKER_POOL_ENABLE)
        # 获得资源池的大小
        self.pool_size = WorkerParams.WORKER_POOL_SIZE
        # 默认超时（<=0 表示不启用超时判定）
        self.run_timeout = WorkerParams.WORKER_RUN_TIMEOUT
        # 资源池初始化
        self.resource_pool = None

        # TODO：将 worker 使用register的方式注册，并且属性和方法都可以通过register的方式注册
        self.workers = []
        # 在飞表：worker 名 -> {worker, run_time, run_timeout, container}
        self.worker_props = {}
        # 在飞表与熔断集合会被派发线程和任务完成回调并发访问
        self._lock = threading.RLock()
        # 已熔断（超时）的 worker 名，不再派发
        self._broken: set = set()
        # 停机标记
        self._stopped = False

        self.register_handler()

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

    def init_lock(self):
        pass

    # 集结worker们
    def call_workers(self, worker_list: list):
        """集结worker们。

        Args:
            worker_list: 参与调度的 Worker 列表
        """
        self.workers = list(worker_list)

        # 生成池或者列表，这里使用线程池，如果使用进程池，需要考虑进程间通信，暂时不考虑
        if (
            self.worker_mode == WaiterConstant.WORKER_MODE_THREAD_POOL
            and self.resource_pool is None
        ):
            self.resource_pool = ThreadPoolExecutor(
                max_workers=self.pool_size, thread_name_prefix="zoo-worker"
            )

    def add_worker(self, worker):
        """把运行期新增的 Worker 纳入调度。

        调度列表由调度器持有，仅在注册表登记不足以让 Worker 被派发。

        Args:
            worker: 待加入调度的 Worker
        """
        if worker is None:
            return
        with self._lock:
            if worker not in self.workers:
                self.workers.append(worker)

    def __del__(self):
        # 释放阶段不做任何可能抛异常的清理：__del__ 抛出的异常只会打印到 stderr
        with contextlib.suppress(Exception):
            self.shutdown(wait=False)

    # 执行服务
    def execute_service(self):
        """执行服务。

        本轮结束后仍保留在调度列表中的，只有声明循环且未被熔断的 Worker。
        """
        if self._stopped:
            return

        # 参与下次循环的worker
        next_loop_workers = []
        for worker in list(self.workers):
            # 非法调度项直接忽略，MUST NOT 因其抛出属性访问异常
            if worker is None:
                continue

            # 超时判定先于在飞判定：判定为超时的 Worker 本轮即被熔断
            self._reap_timeout(worker)

            if self._is_broken(worker):
                continue

            if worker.is_loop:
                next_loop_workers.append(worker)

            if self._is_inflight(worker):
                continue

            self._dispatch_worker(worker)

        self.workers = next_loop_workers

    def _dispatch_worker(self, worker):
        """派遣 worker。

        登记 MUST 先于派发，否则瞬时完成的任务会在登记之前就完成注销。

        Args:
            worker: 待派发的 Worker
        """
        handle = {
            "worker": worker,
            "run_time": time.monotonic(),
            "run_timeout": self._resolve_run_timeout(worker),
            "container": None,
        }

        with self._lock:
            if worker.name in self.worker_props:
                return
            self.worker_props[worker.name] = handle

        try:
            if self.worker_mode == WaiterConstant.WORKER_MODE_THREAD_POOL:
                self._dispatch_to_pool(worker, handle)
            else:
                self._dispatch_to_thread(worker, handle)
        except Exception as e:
            # 派发失败不得中断整轮调度；清掉登记以便下一轮重试
            with self._lock:
                self.worker_props.pop(worker.name, None)
            LogUtils.error(f"Worker {worker.name} 派发失败: {e}", self.__class__.__name__)

    def _dispatch_to_pool(self, worker, handle):
        """资源池模式派发。"""
        future = self.resource_pool.submit(self.worker_running, worker)
        with self._lock:
            handle["container"] = future
        future.add_done_callback(lambda f, w=worker: self._on_future_done(w, f))

    def _dispatch_to_thread(self, worker, handle):
        """线程模式派发。

        与资源池模式共用同一个完成收口，因此线程模式的结果同样会被投递。
        """

        def _run(w=worker):
            try:
                result = self.worker_running(w)
            except Exception as e:
                self._on_worker_done(w, error=e)
            else:
                self._on_worker_done(w, result=result)

        thread = threading.Thread(target=_run, name=f"zoo-{worker.name}", daemon=True)
        with self._lock:
            handle["container"] = thread
        thread.start()

    def _on_future_done(self, worker, future):
        """资源池模式下任务完成的收口。"""
        try:
            result = future.result()
        except Exception as e:
            self._on_worker_done(worker, error=e)
        else:
            self._on_worker_done(worker, result=result)

    def _on_worker_done(self, worker, result=None, error=None):
        """唯一的完成收口：注销在飞状态，并在成功时上报结果。

        无论执行成功与否都必须注销；上报过程自身抛出的异常 MUST NOT 影响注销。

        Args:
            worker: 完成执行的 Worker
            result: 执行结果；执行失败时为 None
            error: 执行时抛出的异常；成功时为 None
        """
        with self._lock:
            self.worker_props.pop(worker.name, None)

        if error is not None:
            LogUtils.error(f"Worker {worker.name} 执行失败: {error}", self.__class__.__name__)
            return

        if result is None:
            return

        try:
            EventReactorManager().dispatch(result.topic, result)
        except Exception as e:
            LogUtils.error(f"Worker {worker.name} 结果上报失败: {e}", self.__class__.__name__)

    def _resolve_run_timeout(self, worker):
        """解析 Worker 的超时：自报 → 按 Worker 名覆盖 → 全局默认。

        Args:
            worker: 目标 Worker

        Returns:
            超时秒数；未声明时返回 None
        """
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

        return self.run_timeout or None

    def _reap_timeout(self, worker):
        """超时判定与熔断。

        只做观测与熔断：记录、标记为不健康、不再派发。MUST NOT 声称已终止仍在
        执行的 Worker —— CPython 无法安全中断一个正在执行的线程。

        Args:
            worker: 目标 Worker
        """
        with self._lock:
            handle = self.worker_props.get(worker.name)
            if handle is None:
                return
            timeout = handle.get("run_timeout")
            if not timeout or timeout <= 0:
                return
            elapsed = time.monotonic() - handle.get("run_time", 0)
            if elapsed < timeout:
                return
            self._broken.add(worker.name)
            self.worker_props.pop(worker.name, None)

        LogUtils.error(
            f"Worker {worker.name} 执行已超过 {timeout}s（实际 {elapsed:.3f}s），"
            "标记为不健康并停止派发；注意：系统不会强制终止仍在执行的 Worker",
            self.__class__.__name__,
        )

    def _is_inflight(self, worker) -> bool:
        with self._lock:
            return worker.name in self.worker_props

    def _is_broken(self, worker) -> bool:
        with self._lock:
            return worker.name in self._broken

    def shutdown(self, wait: bool = True, timeout: float | None = None) -> None:
        """停机：停止派发并回收调度占用的线程资源。

        MUST 可重复调用。

        Args:
            wait: 是否等待在飞任务结束
            timeout: 等待上限（秒）；None 表示不设上限
        """
        with self._lock:
            already_stopped = self._stopped
            self._stopped = True

        if already_stopped:
            return

        LogUtils.info("Waiter 停机中", self.__class__.__name__)

        pool = self.resource_pool
        self.resource_pool = None

        if pool is not None:
            # cancel_futures 只对尚未开始的任务生效；已开始的任务无法中断，只能等
            pool.shutdown(wait=False, cancel_futures=True)
            if wait:
                self._join_pool_threads(pool, timeout)

        with self._lock:
            self.workers = []
            self.worker_props.clear()

    @staticmethod
    def _join_pool_threads(pool, timeout: float | None) -> None:
        """在给定上限内等待资源池的工作线程退出。

        使用 ThreadPoolExecutor 的私有 ``_threads``：公开 API 未提供带超时的等待，
        而停机 MUST NOT 无限期阻塞。
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        for thread in list(getattr(pool, "_threads", ())):
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                LogUtils.warning(
                    f"停机等待超时，仍有工作线程未退出（等待上限 {timeout}s）",
                    BaseWaiter.__name__,
                )
                return
            thread.join(remaining)

    def register_worker(self, worker, worker_container):
        """Register the worker to self.worker_props

        Args:
            worker: worker
            worker_container: worker running thread or process
        """
        self.worker_props[worker.name] = {
            "worker": worker,
            "run_time": time.monotonic(),
            "run_timeout": worker.run_timeout,
            "container": worker_container,
        }

    def unregister_worker(self, worker):
        with self._lock:
            self.worker_props.pop(worker.name, None)

    # 派遣worker
    @staticmethod
    def worker_running(worker):
        """派遣worker。

        Returns:
            WorkerResult；worker 非法时返回 None
        """
        if not isinstance(worker, BaseWorker):
            return None

        return worker.run()
