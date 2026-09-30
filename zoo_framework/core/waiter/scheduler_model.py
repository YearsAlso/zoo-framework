"""调度模型：声明契约并拥有并发原语与调度轮形状.

模型契约六项 MUST 可被程序化查询（``describe()``）：

1. 并发原语 ``concurrency_primitive``
2. **支持的时间语义** ``supported_time_semantics``
3. 背压策略 ``backpressure_policy``
4. 停机语义 ``stop_semantics``
5. 支持的 Worker 类别 ``supported_worker_kinds``
6. 可观测指标 ``observable_metrics``

"支持的时间语义"声明的是**本模型能够调度哪些时间语义**，MUST NOT 被理解为把整个
进程钉在某一种语义上：周期与相位由 **Worker 逐个声明**，同一模型下 MUST 可以同时
调度周期驱动与事件驱动的 Worker（设备场景的周期控制回路与事件驱动报警处理器共存
正是如此）。周期排期本身与并发原语无关，由
:class:`~zoo_framework.core.waiter.dispatch_core.WorkerDispatchCore` 承担。

模型**只负责**"怎么把 Worker 派出去、怎么回收容器"。任何模型无关的正确性逻辑——
单一结算收口、超时观测与熔断、停机回收、运行期注册、周期排期判断——MUST NOT 在本层
重新实现。
"""

import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

from zoo_framework.constant import WorkerConstant
from zoo_framework.utils import LogUtils

from ..run_identity import carry_context

# ---------------------------------------------------------------- 契约取值

# 并发原语
CONCURRENCY_THREAD_PER_TASK = "thread_per_task"
CONCURRENCY_THREAD_POOL = "thread_pool"
CONCURRENCY_EVENT_LOOP = "event_loop"
CONCURRENCY_PROCESS = "process"  # 未实现

# 时间语义
TIME_SEMANTICS_EVENT_DRIVEN = "event_driven"
TIME_SEMANTICS_PERIODIC = "periodic"

# 背压策略（同时就是"池尺寸不足时怎么办"的取值）
BACKPRESSURE_UNBOUNDED = "unbounded"  # 不受限，每次派发都起新线程
BACKPRESSURE_QUEUE = "queue"  # 池尺寸不变，超出部分在池中排队
BACKPRESSURE_EXPAND = "expand"  # 自动把池尺寸放宽到 Worker 数 + 1
BACKPRESSURE_REJECT = "reject"  # 超出即拒绝，MUST NOT 静默改写调用方的配置

# 停机语义
STOP_ABANDON_INFLIGHT = "stop_dispatch_abandon_inflight"  # 停止派发；已开始的无法中断
STOP_CANCEL_QUEUED = "stop_dispatch_cancel_queued"  # 停止派发并取消尚未开始的任务

# Worker 类别
WORKER_KIND_SYNC = "sync"
WORKER_KIND_ASYNC = "async"

# 指标名（抖动是**按 Worker** 的观测，经内核 ``jitter(worker)`` 查询）
METRIC_INFLIGHT = "inflight"
METRIC_COMPLETED = "completed"
METRIC_TIMEOUTS = "timeouts"
METRIC_JITTER = "jitter"

#: 配置 ``worker:runPolicy`` 的历史取值 → 池尺寸不足时的背压策略.
#:
#: 三种取值的行为被完整保留（expand / queue / reject），但它们**不再是调度器类的
#: 名字**——差异已由 ``ThreadPoolModel`` 的 ``backpressure_policy`` 参数承载。
#: 未知取值 MUST 被明确拒绝（见 ``BaseWaiter``），MUST NOT 静默降级。
LEGACY_POLICY_TO_BACKPRESSURE = {
    WorkerConstant.RUN_POLICY_SIMPLE: BACKPRESSURE_EXPAND,
    WorkerConstant.RUN_POLICY_STABLE: BACKPRESSURE_QUEUE,
    WorkerConstant.RUN_POLICY_SAFE: BACKPRESSURE_REJECT,
}


class SchedulerModel(ABC):
    """调度模型基类.

    Attributes:
        concurrency_primitive: 并发原语取值之一
        supported_time_semantics: 本模型能够调度的时间语义集合
        backpressure_policy: 背压策略取值之一
        stop_semantics: 停机语义取值之一
        supported_worker_kinds: 支持的 Worker 类别
        observable_metrics: 本模型可提供的运行期指标名
    """

    concurrency_primitive: str = ""
    supported_time_semantics: tuple = ()
    backpressure_policy: str = ""
    stop_semantics: str = ""
    supported_worker_kinds: tuple = ()
    observable_metrics: tuple = (
        METRIC_INFLIGHT,
        METRIC_COMPLETED,
        METRIC_TIMEOUTS,
        METRIC_JITTER,
    )

    def describe(self) -> dict:
        """六项契约的可程序化查询入口.

        以**实例**为单位：背压策略等项可能随实例参数变化（``ThreadPoolModel``），
        若做成类方法会读到类级空值、掩盖实例的真实声明。

        Returns:
            含六项声明的字典；任一项为空表示该模型未正确声明
        """
        return {
            "concurrency_primitive": self.concurrency_primitive,
            "supported_time_semantics": list(self.supported_time_semantics),
            "backpressure_policy": self.backpressure_policy,
            "stop_semantics": self.stop_semantics,
            "supported_worker_kinds": list(self.supported_worker_kinds),
            "observable_metrics": list(self.observable_metrics),
        }

    @abstractmethod
    def start(self, core) -> None:
        """启动模型（创建容器），并置为已启动.

        每个模型 MUST 自行实现：``submit`` 的前置条件是已启动，两种模型对
        "未启动即提交"的处理应当一致（拒绝，而不是静默失败）。
        """

    @abstractmethod
    def submit(self, core, worker) -> None:
        """把 Worker 派发出去.

        实现 MUST 在完成时调用 ``core.settle``，使结算走单一收口。
        """

    @abstractmethod
    def prepare_workers(self, workers) -> int:
        """在创建容器**之前**按背压策略处理 Worker 列表.

        MUST 在容器创建前调用：``expand`` 语义要求放宽后的尺寸在建池时生效。

        Returns:
            本模型实际使用的容量（无容器概念时返回 0）
        """

    @abstractmethod
    def teardown(self, core, wait: bool = True, timeout: float | None = None) -> None:
        """回收容器，并置为未启动. MUST 可重复调用."""


class ThreadPerTaskModel(SchedulerModel):
    """每个任务一个线程：无背压，派发不阻塞调度轮.

    对应既有 ``worker:mode=thread``。已派发任务的线程为 daemon，停机时**放弃**在飞
    任务而非等待（CPython 无法安全中断正在执行的线程）。
    """

    concurrency_primitive = CONCURRENCY_THREAD_PER_TASK
    supported_time_semantics = (TIME_SEMANTICS_EVENT_DRIVEN, TIME_SEMANTICS_PERIODIC)
    backpressure_policy = BACKPRESSURE_UNBOUNDED
    stop_semantics = STOP_ABANDON_INFLIGHT
    supported_worker_kinds = (WORKER_KIND_SYNC,)

    def __init__(self):
        self._started = False

    def start(self, core) -> None:
        """无线程池容器可建；置为已启动，使 submit 的前置条件可校验."""
        self._started = True

    def teardown(self, core, wait: bool = True, timeout: float | None = None) -> None:
        """已派发的 daemon 线程按停机语义被放弃，无容器可回收；置为未启动."""
        self._started = False

    def prepare_workers(self, workers) -> int:
        """本模型每次派发一个独立线程，**无容量概念**，故不做任何限制并返回 0.

        背压策略为 ``unbounded``：不因 Worker 数量而拒绝、也不排队。
        """
        return 0

    def submit(self, core, worker) -> None:
        if not self._started:
            raise RuntimeError("模型尚未启动（start 未被调用）")

        # 显式携带调度方的上下文：新建线程不会继承调用方的 ContextVar，
        # 不经 carry_context 会让工作线程里的运行标识静默丢失
        thread = threading.Thread(
            target=carry_context(core.run_and_settle),
            args=(worker,),
            name=f"zoo-{worker.name}",
            daemon=True,
        )
        core.attach_container(worker, thread)
        thread.start()


class ThreadPoolModel(SchedulerModel):
    """线程池：并发数有上界，池尺寸不足时按``backpressure_policy``处理.

    对应既有 ``worker:mode=thread_pool``。三种背压策略吸收了原
    ``SimpleWaiter`` / ``StableWaiter`` / ``SafeWaiter`` 的**唯一**差异：
    expand / queue / reject。
    """

    concurrency_primitive = CONCURRENCY_THREAD_POOL
    supported_time_semantics = (TIME_SEMANTICS_EVENT_DRIVEN, TIME_SEMANTICS_PERIODIC)
    stop_semantics = STOP_CANCEL_QUEUED
    supported_worker_kinds = (WORKER_KIND_SYNC,)

    def __init__(self, pool_size: int, backpressure_policy: str = BACKPRESSURE_EXPAND):
        """初始化线程池模型.

        Args:
            pool_size: 资源池尺寸
            backpressure_policy: 池尺寸不足时的处理策略（queue / expand / reject）

        Raises:
            ValueError: 背压策略不在取值范围内
        """
        if backpressure_policy not in (
            BACKPRESSURE_QUEUE,
            BACKPRESSURE_EXPAND,
            BACKPRESSURE_REJECT,
        ):
            raise ValueError(
                f"不支持的背压策略 {backpressure_policy!r}；可选 "
                f"{[BACKPRESSURE_QUEUE, BACKPRESSURE_EXPAND, BACKPRESSURE_REJECT]}"
            )
        self.pool_size = pool_size
        self.backpressure_policy = backpressure_policy
        # 实际生效的池尺寸（expand 策略会放宽它，但**不改动** pool_size 本身——
        # 调用方配置的意图 MUST 保持可读）
        self.effective_pool_size = pool_size
        self._pool: ThreadPoolExecutor | None = None

    def prepare_workers(self, workers) -> int:
        """按背压策略处理"Worker 数超过池尺寸"的情形.

        必须在池创建**之前**调用——``expand`` 语义要求放宽后的尺寸在建池时生效。

        Args:
            workers: 即将参与调度的 Worker 列表

        Returns:
            本模型实际使用的池尺寸

        Raises:
            ValueError: 背压策略为 reject 且 Worker 数超过池尺寸
        """
        count = len([worker for worker in workers if worker is not None])
        if count <= self.effective_pool_size:
            return self.effective_pool_size

        if self.backpressure_policy == BACKPRESSURE_REJECT:
            raise ValueError(
                f"Worker 数量 {count} 超过资源池尺寸 {self.pool_size}；"
                "请增大 worker:pool:size，或将池尺寸不足时的策略改为 expand / queue"
            )
        if self.backpressure_policy == BACKPRESSURE_EXPAND:
            self.effective_pool_size = count + 1
        # queue：尺寸不变，超出部分在池内排队
        return self.effective_pool_size

    def start(self, core) -> None:
        if self._pool is None:
            self._pool = ThreadPoolExecutor(
                max_workers=self.effective_pool_size, thread_name_prefix="zoo-worker"
            )

    def submit(self, core, worker) -> None:
        if self._pool is None:
            raise RuntimeError("模型尚未启动（start 未被调用）")
        # 线程池任务同样不会继承调用方的上下文，故与线程模式一样显式携带
        future = self._pool.submit(carry_context(core.run_and_settle), worker)
        core.attach_container(worker, future)
        future.add_done_callback(self._log_unexpected_failure)

    @staticmethod
    def _log_unexpected_failure(future) -> None:
        """执行单元自身不应抛异常.

        它内部已捕获 Worker 的异常并结算；若仍有异常逃逸（例如结算路径的缺陷），
        必须留下痕迹——线程池会把未观察的异常静默丢掉。
        """
        if future.cancelled():
            return
        error = future.exception()
        if error is not None:
            LogUtils.error(
                f"调度执行单元异常（非 Worker 自身异常）: {error}", ThreadPoolModel.__name__
            )

    def teardown(self, core, wait: bool = True, timeout: float | None = None) -> None:
        pool = self._pool
        self._pool = None
        if pool is None:
            return
        # cancel_futures 只对尚未开始的任务生效；已开始的任务无法中断，只能等
        pool.shutdown(wait=False, cancel_futures=True)
        if wait:
            self._join_pool_threads(pool, timeout)

    @staticmethod
    def _join_pool_threads(pool, timeout: float | None) -> None:
        """在给定上限内等待资源池的工作线程退出.

        使用单调时钟的**总预算**语义：``timeout`` 是所有线程共享的等待上限，
        MUST NOT 被当成每个线程各自的上限（那会让等待时长随线程数增长）。
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        for thread in list(getattr(pool, "_threads", ())):
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return
            thread.join(remaining)
