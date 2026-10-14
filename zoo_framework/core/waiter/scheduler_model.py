"""Scheduling models: declare contracts and own the concurrency primitive and round shape.

The six contract items MUST be programmatically queryable (``describe()``):

1. concurrency primitive ``concurrency_primitive``
2. **supported time semantics** ``supported_time_semantics``
3. backpressure policy ``backpressure_policy``
4. stop semantics ``stop_semantics``
5. supported Worker kinds ``supported_worker_kinds``
6. observable metrics ``observable_metrics``

"Supported time semantics" declares **which time semantics this model can
schedule**, and MUST NOT be read as pinning the whole process to one semantics:
period and phase are declared **per Worker**, and one model MUST be able to
schedule periodic-driven and event-driven Workers at the same time (a device
scenario with periodic control loops coexisting with event-driven alarm
handlers is exactly that). Period scheduling itself is independent of the
concurrency primitive; it is owned by
:class:`~zoo_framework.core.waiter.dispatch_core.WorkerDispatchCore`.

A model is **only responsible for** "how to send Workers out and how to reclaim
the concurrency container". Any model-agnostic correctness logic - the single
settlement path, timeout observation and circuit-breaking, shutdown reclamation,
runtime registration, period scheduling - MUST NOT be re-implemented at this
layer.
"""

import asyncio
import contextlib
import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

from zoo_framework.constant import WaiterConstant, WorkerConstant
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker
from zoo_framework.workers.async_worker import AsyncWorker

from ..run_identity import carry_context

# ---------------------------------------------------------------- 契约取值

# Concurrency primitives
CONCURRENCY_THREAD_PER_TASK = "thread_per_task"
CONCURRENCY_THREAD_POOL = "thread_pool"
CONCURRENCY_EVENT_LOOP = "event_loop"
CONCURRENCY_PROCESS = "process"  # 未实现

# Time semantics
TIME_SEMANTICS_EVENT_DRIVEN = "event_driven"
TIME_SEMANTICS_PERIODIC = "periodic"

# Backpressure policies (also the "what to do when workers exceed the pool size" values)
BACKPRESSURE_UNBOUNDED = "unbounded"  # unbounded: a new thread per dispatch
BACKPRESSURE_QUEUE = "queue"  # keep the pool size; extras queue inside the pool
BACKPRESSURE_EXPAND = "expand"  # widen the pool to worker count + 1
BACKPRESSURE_REJECT = "reject"  # refuse the excess; MUST NOT silently rewrite caller config

# Stop semantics
STOP_ABANDON_INFLIGHT = (
    "stop_dispatch_abandon_inflight"  # stop dispatching; started tasks cannot be interrupted
)
STOP_CANCEL_QUEUED = (
    "stop_dispatch_cancel_queued"  # stop dispatching and cancel not-yet-started tasks
)

# Worker kinds
WORKER_KIND_SYNC = "sync"
WORKER_KIND_ASYNC = "async"

# Metric names (jitter is **per-Worker** observation, queried via core ``jitter(worker)``)
METRIC_INFLIGHT = "inflight"
METRIC_COMPLETED = "completed"
METRIC_TIMEOUTS = "timeouts"
METRIC_JITTER = "jitter"

#: Legacy values of config ``worker:runPolicy`` -> the backpressure policy for
#: an undersized pool.
#:
#: The behavior of the three values is fully preserved (expand / queue /
#: reject), but they are **no longer the names of scheduler classes** - the
#: difference is now carried by ``ThreadPoolModel``'s ``backpressure_policy``
#: parameter. Unknown values MUST be rejected explicitly (see ``BaseWaiter``)
#: and MUST NOT be silently downgraded.
LEGACY_POLICY_TO_BACKPRESSURE = {
    WorkerConstant.RUN_POLICY_SIMPLE: BACKPRESSURE_EXPAND,
    WorkerConstant.RUN_POLICY_STABLE: BACKPRESSURE_QUEUE,
    WorkerConstant.RUN_POLICY_SAFE: BACKPRESSURE_REJECT,
}


class SchedulerModel(ABC):
    """Scheduling model base class.

    Attributes:
        concurrency_primitive: one of the concurrency primitive values
        supported_time_semantics: the time semantics this model can schedule
        backpressure_policy: one of the backpressure policy values
        stop_semantics: one of the stop semantics values
        supported_worker_kinds: the supported Worker kinds
        observable_metrics: the runtime metric names this model can expose
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
        """The programmatic query entry for the six contract items.

        Per **instance**: items like the backpressure policy may vary with
        instance arguments (``ThreadPoolModel``); a classmethod would read the
        class-level empty values and hide the instance's real declaration.

        Returns:
            A dict with the six declarations; any empty item means the model
            did not declare it correctly
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
        """Start the model (create the container) and mark it started.

        Each model MUST implement this itself: ``submit`` requires a started
        model, and both models should treat "submit before start" the same way
        (refuse, not silently fail).
        """

    @abstractmethod
    def submit(self, core, worker) -> None:
        """Dispatch the Worker.

        Implementations MUST call ``core.settle`` on completion so settlement
        goes through the single path.
        """

    @abstractmethod
    def prepare_workers(self, workers) -> int:
        """Process the Worker list according to the backpressure policy **before** creating the container.

        MUST be called before container creation: ``expand`` semantics require
        the widened size to be in effect when the pool is built.

        Returns:
            The capacity this model actually uses (0 when it has no container
            concept)
        """

    @abstractmethod
    def teardown(self, core, wait: bool = True, timeout: float | None = None) -> None:
        """Reclaim the container and mark the model not started. MUST be repeatable."""


class ThreadPerTaskModel(SchedulerModel):
    """One thread per task: no backpressure, dispatch never blocks the scheduling round.

    Corresponds to the existing ``worker:mode=thread``. Dispatched task threads
    are daemon threads; at shutdown in-flight tasks are **abandoned** rather
    than awaited (CPython cannot safely interrupt a running thread).
    """

    concurrency_primitive = CONCURRENCY_THREAD_PER_TASK
    supported_time_semantics = (TIME_SEMANTICS_EVENT_DRIVEN, TIME_SEMANTICS_PERIODIC)
    backpressure_policy = BACKPRESSURE_UNBOUNDED
    stop_semantics = STOP_ABANDON_INFLIGHT
    supported_worker_kinds = (WORKER_KIND_SYNC,)

    def __init__(self):
        self._started = False

    def start(self, core) -> None:
        """No thread-pool container to build; mark started so ``submit``'s precondition can be checked."""
        self._started = True

    def teardown(self, core, wait: bool = True, timeout: float | None = None) -> None:
        """Dispatched daemon threads are abandoned per the stop semantics; no container to reclaim; mark not started."""
        self._started = False

    def prepare_workers(self, workers) -> int:
        """This model starts an independent thread per dispatch with **no capacity concept**, so no limits apply and 0 is returned.

        The backpressure policy is ``unbounded``: never refuses because of the
        worker count and never queues.
        """
        return 0

    def submit(self, core, worker) -> None:
        if not self._started:
            raise RuntimeError("model not started (start() has not been called)")

        # Carry the dispatcher's context explicitly: a new thread does not inherit
        # the caller's ContextVars; without carry_context the run identity would
        # be silently lost inside the worker thread
        thread = threading.Thread(
            target=carry_context(core.run_and_settle),
            args=(worker,),
            name=f"zoo-{worker.name}",
            daemon=True,
        )
        core.attach_container(worker, thread)
        thread.start()


class ThreadPoolModel(SchedulerModel):
    """Thread pool: bounded concurrency, handling undersized pools via ``backpressure_policy``.

    Corresponds to the existing ``worker:mode=thread_pool``. The three
    backpressure policies absorb the **only** difference among the former
    ``SimpleWaiter`` / ``StableWaiter`` / ``SafeWaiter``: expand / queue /
    reject.

    Container implementation (change replace-pool-dispatch-queue / #47 P2):
    fixed worker threads + a ``queue.Queue`` task queue, replacing the old
    ``concurrent.futures.ThreadPoolExecutor`` - measurements showed Future
    bookkeeping dominates the dispatch cost (submit().result() 31.9 us vs
    1.86 us via the queue directly, bench/DECISION.md section 4). The six
    contract items and the three backpressure semantics are unchanged item by
    item: bound = thread count, queue = unbounded FIFO, stop-cancel-queued =
    discard not-yet-started tasks.
    """

    concurrency_primitive = CONCURRENCY_THREAD_POOL
    supported_time_semantics = (TIME_SEMANTICS_EVENT_DRIVEN, TIME_SEMANTICS_PERIODIC)
    stop_semantics = STOP_CANCEL_QUEUED
    supported_worker_kinds = (WORKER_KIND_SYNC,)

    def __init__(self, pool_size: int, backpressure_policy: str = BACKPRESSURE_EXPAND):
        """Initialize the thread pool model.

        Args:
            pool_size: the pool size
            backpressure_policy: the policy for undersized pools (queue /
                expand / reject)

        Raises:
            ValueError: the backpressure policy is not one of the legal values
        """
        if backpressure_policy not in (
            BACKPRESSURE_QUEUE,
            BACKPRESSURE_EXPAND,
            BACKPRESSURE_REJECT,
        ):
            raise ValueError(
                f"unsupported backpressure policy {backpressure_policy!r}; expected "
                f"{[BACKPRESSURE_QUEUE, BACKPRESSURE_EXPAND, BACKPRESSURE_REJECT]}"
            )
        self.pool_size = pool_size
        self.backpressure_policy = backpressure_policy
        # The actually effective pool size (the expand policy widens it but does
        # **not** modify pool_size itself - the caller's configured intent MUST
        # stay readable)
        self.effective_pool_size = pool_size
        # Task queue + fixed worker threads (the "cancel queued" of
        # stop_semantics=stop_dispatch_cancel_queued is implemented by teardown
        # discarding not-yet-started tasks; clearing the in-flight table is the
        # core's shutdown responsibility)
        self._tasks: queue.Queue | None = None
        self._threads: list[threading.Thread] = []

    def prepare_workers(self, workers: list[BaseWorker | None]) -> int:
        """Handle "worker count exceeds the pool size" according to the backpressure policy.

        Called **before** the pool is created at startup - ``expand`` semantics
        require the widened size to be in effect when the pool is built. It is
        also the admission entry for **runtime** registration (``BaseWaiter.add_worker``,
        issue #233): when the pool is already running, the widened size MUST be
        applied to the live container as well, or ``expand`` would only bump a
        number that has no effect (a silent no-op).

        Args:
            workers: the Worker list about to participate in scheduling

        Returns:
            The pool size this model actually uses

        Raises:
            ValueError: the policy is reject and the worker count exceeds the
                pool size
        """
        count = len([worker for worker in workers if worker is not None])
        if count <= self.effective_pool_size:
            return self.effective_pool_size

        if self.backpressure_policy == BACKPRESSURE_REJECT:
            raise ValueError(
                f"worker count {count} exceeds the pool size {self.pool_size};"
                "increase worker:pool:size, or switch the undersized-pool policy to expand / queue"
            )
        if self.backpressure_policy == BACKPRESSURE_EXPAND:
            self.effective_pool_size = count + 1
            # 运行期注册时容器可能已在运行：把放宽后的容量真正应用到活的池，
            # 否则数字变了却没有效果（静默 no-op）。启动期（_tasks 为 None）由
            # 随后的 start 建池，无需在此建。
            if self._tasks is not None:
                self._ensure_threads(self.effective_pool_size)
        # queue: the size stays; the excess queues inside the pool
        return self.effective_pool_size

    def start(self, core) -> None:
        """Build the queue and worker threads at the **current** effective size (sized by prepare_workers before start).

        Idempotent: when the container already exists, the thread count is
        reconciled up to the effective size (the runtime ``expand`` path widens
        it via ``prepare_workers``) - threads are never removed here, shrinking
        is ``teardown``'s job.
        """
        if self._tasks is None:
            if self.effective_pool_size <= 0:
                # Aligned with the old ThreadPoolExecutor(max_workers<=0) error
                # behavior: an illegal size is refused on the spot; MUST NOT silently
                # build a zero-thread pool so that submit never finds a "started"
                # container
                raise ValueError(
                    f"pool size must be positive, got {self.effective_pool_size} (config key worker:pool:size)"
                )
            self._tasks = queue.Queue()
        self._ensure_threads(self.effective_pool_size)

    def _ensure_threads(self, target: int) -> None:
        """Grow the worker-thread count up to ``target`` (``_tasks`` must exist).

        New threads take indices from the current length, so names stay
        ``zoo-worker-<n>``. Threads are only ever **added** here: shrinking is
        ``teardown``'s responsibility (it discards queued tasks and reclaims
        every thread).
        """
        tasks = self._tasks
        if tasks is None:
            return
        while len(self._threads) < target:
            thread = threading.Thread(
                target=self._worker_loop,
                args=(tasks,),
                name=f"zoo-worker-{len(self._threads)}",
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()

    @staticmethod
    def _worker_loop(tasks: queue.Queue) -> None:
        """Worker-thread main loop: fetch a task, execute it, observe escaped exceptions in place.

        The execution unit (``core.run_and_settle``) already catches Worker
        exceptions and goes through the single settlement; anything escaping
        this layer is a dispatch-path defect, MUST leave a trace and the thread
        MUST keep serving. None is the shutdown sentinel.
        """
        while True:
            item = tasks.get()
            if item is None:
                return
            run_and_settle, worker = item
            try:
                run_and_settle(worker)
            except Exception as error:  # an escape is a defect; log, do not re-raise, keep serving
                LogUtils.error(
                    f"scheduler execution unit raised (not a Worker's own exception): {error}",
                    ThreadPoolModel.__name__,
                )

    def submit(self, core, worker) -> None:
        if self._tasks is None or not self._threads:
            raise RuntimeError("model not started (start() has not been called)")
        # Worker threads do not inherit the caller's context; like the thread
        # mode, carry it explicitly at the dispatch site
        run_and_settle = carry_context(core.run_and_settle)
        self._tasks.put((run_and_settle, worker))
        core.attach_container(worker, run_and_settle)

    def teardown(self, core, wait: bool = True, timeout: float | None = None) -> None:
        """Shutdown: discard queued not-yet-started tasks (``stop_dispatch_cancel_queued``), then stop the threads.

        Started tasks cannot be interrupted (a CPython limitation, the same as
        the old ThreadPoolExecutor implementation); the in-flight table and the
        scheduling list are cleared by ``core.clear()`` (called from
        BaseWaiter.shutdown).
        """
        tasks, threads = self._tasks, self._threads
        self._tasks, self._threads = None, []
        if tasks is None and not threads:
            return
        if tasks is not None:
            # Discard queued items before putting the sentinels, or a sentinel
            # would be treated as a normal item and dropped, leaving the thread
            # blocked on get() forever
            self._discard_queued(tasks)
            for _ in threads:
                tasks.put(None)
        if wait:
            self._join_threads(threads, timeout)

    @staticmethod
    def _discard_queued(tasks: queue.Queue) -> None:
        """Drain the not-yet-started tasks; their in-flight registrations are settled by core.clear, the same shape as future cancellation."""
        while True:
            try:
                tasks.get_nowait()
            except queue.Empty:
                return

    @staticmethod
    def _join_threads(threads: list[threading.Thread], timeout: float | None) -> None:
        """Wait for the worker threads to exit within the given bound.

        Uses the monotonic-clock **total budget** semantics: ``timeout`` is a
        shared waiting bound for all the threads and MUST NOT be treated as a
        per-thread bound (that would make the wait grow with the thread count).
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        for thread in threads:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return
            thread.join(remaining)


# ---------------------------------------------------------------- 常驻事件循环模型

#: 常驻循环线程名（便于在进程线程列表中识别；与 Master.run 的主线程循环无关）。
LOOP_THREAD_NAME = "zoo-event-loop"

#: 停机时"已在开始前被丢弃"的提交的返回值：不投递结果、不结算。MUST NOT 用 None
#: 代替——None 是合法的业务返回值（协程可以返回 None），复用会让"丢弃"与"返回空值"
#: 不可区分。
_DISCARDED = object()

#: 停止循环后 join 循环线程的默认上限（``timeout`` 未给时），避免停机无限等待。
_LOOP_STOP_TIMEOUT = 5.0

#: ``loop.stop`` 已投递后 join 循环线程的最小宽限：即便算出的剩余预算已耗尽，也留
#: 一小段让 ``run_forever`` 真正返回，否则会因"循环仍在运行"而放弃 ``close``。
_LOOP_STOP_GRACE = 1.0


class _Submission:
    """一次派发的状态：是否已在循环上开始、是否在开始前被停机丢弃。

    停机据此区分两条互斥的处置：``started`` 为真者在界内等它结算、MUST NOT 中断；
    为假者在循环取到之前丢弃、MUST NOT 再执行。判定与写入共用 ``EventLoopModel``
    的锁，保证"开始"与"丢弃"不会同时成立（否则会丢结果或重启一个已丢弃的协程）。
    """

    __slots__ = ("discarded", "started")

    def __init__(self) -> None:
        self.started = False
        self.discarded = False


class EventLoopModel(SchedulerModel):
    """常驻事件循环模型：在独立守护线程上常驻一个事件循环，把协程 Worker 投给它执行。

    与 ``ThreadPerTaskModel`` / ``ThreadPoolModel`` 并列的第三个执行模型，对应
    ``worker:mode=event_loop``。它解决的是**等待**而不是计算：同一个 Worker 可以
    同时推进多个等待中的调用，而工作线程数不随并发增长（所有协程共享一条循环线程，
    并发上限由 Worker 侧的 ``asyncio.Semaphore(max_concurrent)`` 决定）。

    同步或 CPU 密集的执行体 MUST NOT 进入循环线程——循环线程被占住会让**所有**协程
    与取消一起停摆。因此本模型只接纳协程能力 Worker（``AsyncWorker`` 子类），其余在
    ``prepare_workers`` 阶段**显式拒绝**，MUST NOT 静默改用其它模型、MUST NOT 自动
    改派线程池。

    停机语义 ``stop_dispatch_cancel_queued``：先使新派发被拒绝，再在给定界内等待在飞
    协程结算，最后停止并关闭循环。已开始执行的协程不被中断（向协程投递取消请求不等价
    于它已经停止）；已提交但尚未开始的协程在停机时被丢弃。
    """

    concurrency_primitive = CONCURRENCY_EVENT_LOOP
    supported_time_semantics = (TIME_SEMANTICS_EVENT_DRIVEN, TIME_SEMANTICS_PERIODIC)
    # 本模型不引入自己的背压档位：循环照单接收每次派发（容量由 Worker 侧信号量决定），
    # 与 ThreadPerTaskModel 的 "unbounded" 同义。与 #233 的运行时注册背压对齐列为待观察项。
    backpressure_policy = BACKPRESSURE_UNBOUNDED
    stop_semantics = STOP_CANCEL_QUEUED
    supported_worker_kinds = (WORKER_KIND_ASYNC,)

    def __init__(self) -> None:
        self._started = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        # 每次派发的在飞登记：concurrent.futures.Future -> _Submission。与核心的在飞表
        # 无关（那张表由 WorkerDispatchCore 持有），这里只用于停机时区分"已开始 / 未开始"。
        self._pending: dict[Any, _Submission] = {}
        self._lock = threading.RLock()

    def prepare_workers(self, workers: list[BaseWorker | None]) -> int:
        """准入裁决：只接纳协程能力 Worker，其余显式拒绝。

        与 ``thread_pool`` 不同，本模型没有"池尺寸"这一容量概念，故返回 0；但对 Worker
        类别做硬裁决：非协程 Worker MUST 被明确拒绝并指出不兼容之处与可选模型
        （``scheduler-model`` 规格「模型选择 MUST 显式且不做降级」）。这同时堵住
        "CPU 密集 Worker 误配 event_loop"这一事故形态。

        Args:
            workers: 即将参与调度的 Worker 列表

        Returns:
            0（本模型无容器容量概念）

        Raises:
            ValueError: 列表中存在不具备协程能力的 Worker
        """
        for worker in workers:
            if worker is None or isinstance(worker, AsyncWorker):
                continue
            raise ValueError(
                f"Worker {getattr(worker, 'name', worker)!r} ({type(worker).__name__}) "
                f"does not declare coroutine capability; the {CONCURRENCY_EVENT_LOOP} "
                "model only accepts async Workers (AsyncWorker subclasses) so that a "
                "synchronous blocking body never occupies the event-loop thread. "
                f"Use worker:mode={WaiterConstant.WORKER_MODE_THREAD} or "
                f"{WaiterConstant.WORKER_MODE_THREAD_POOL} for synchronous Workers."
            )
        return 0

    def start(self, core) -> None:
        """启动常驻循环：新建事件循环并在独立守护线程上 ``run_forever``。

        容器在 ``start`` 而非 ``__init__`` 建立——模型的生命周期归 ``start``，与
        ``ThreadPoolModel.start`` 建池同形。幂等：已启动时不再新建，避免泄漏第二条循环线程。
        """
        with self._lock:
            if self._started:
                return
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=loop.run_forever,
                name=LOOP_THREAD_NAME,
                daemon=True,
            )
            self._loop = loop
            self._thread = thread
            self._started = True
            thread.start()

    def submit(self, core, worker) -> None:
        """把 Worker 的异步执行体投给常驻循环。

        派发发生在 ``Master.run()`` 的主线程循环里，而协程交给**另一个线程上的另一个
        loop**——两者 MUST NOT 混用，故跨线程提交用 ``asyncio.run_coroutine_threadsafe``
        （该 API 本身即线程安全）。完成回调在循环线程上执行，并经由 ``core.settle``
        这一唯一出口结算。

        Raises:
            RuntimeError: 模型未启动（含停机之后），拒绝派发
        """
        loop = self._loop
        if not self._started or loop is None:
            raise RuntimeError("model not started (start() has not been called)")

        submission = _Submission()
        future = asyncio.run_coroutine_threadsafe(self._runner(worker, submission), loop)
        with self._lock:
            self._pending[future] = submission
        core.attach_container(worker, future)
        future.add_done_callback(lambda done: self._on_complete(core, worker, submission, done))

    async def _runner(self, worker: AsyncWorker, submission: _Submission) -> Any:
        """循环线程上的执行体：在开始前被停机丢弃的提交不执行。

        第一行在锁内声明"已开始"——停机据此区分"已开始（等它结算）"与"尚未开始（丢弃）"。
        两处判定共用一把锁，使"开始"与"丢弃"互斥，不会出现"协程跑了却没有结果"的静默丢失。
        """
        with self._lock:
            if submission.discarded:
                return _DISCARDED
            submission.started = True
        return await worker._execute_async()

    def _on_complete(self, core, worker: AsyncWorker, submission: _Submission, future: Any) -> None:
        """完成回调（循环线程）：结算走 ``core.settle`` 唯一出口。

        停机时被丢弃、未开始执行的提交不结算——其登记由 ``core.clear`` 清除，若在此再
        投递结果，就会为一次从未执行的提交产生假结果。
        """
        with self._lock:
            self._pending.pop(future, None)

        if submission.discarded:
            return

        value: Any = None
        error: BaseException | None = None
        try:
            value = future.result()
        except BaseException as exc:  # 含 CancelledError：失败同样走共用的结果契约
            error = exc

        core.settle(worker, result=worker.build_result(value, error))

    def teardown(self, core, wait: bool = True, timeout: float | None = None) -> None:
        """停机：先拒新派发 → 界内等在飞结算 → 停循环 → 关循环。MUST 可重复调用。

        次序是硬约束：MUST 先等在飞协程结算完再停循环，否则结算回调永不执行、结果不
        投递、在飞表残留。已开始的协程不被中断；已提交但尚未开始的协程被丢弃
        （``stop_dispatch_cancel_queued``）。

        在飞表与结算收口由入参 ``core``（派发核心）持有，本模型只按它给出的契约调用；
        ``wait`` / ``timeout`` 分别是"是否等在飞结算"与"等待的总预算"。

        本方法**故意不写 ``Args:`` 段**（与 ``ThreadPerTaskModel`` / ``ThreadPoolModel``
        的 ``teardown`` 同形）：``core`` 没有类型注解，一旦列出就会被 griffe 在
        ``mkdocs build --strict`` 下判为「参数无注解」告警；而不列出又会被 ruff 的
        ``D417`` 判为「参数缺少说明」。去掉整个 ``Args:`` 段可同时满足两者。
        """
        with self._lock:
            loop, thread = self._loop, self._thread
            pending = list(self._pending.items())
            # ① 先置"未启动"，使 submit 按既有契约拒绝新派发；并摘除容器引用，重复调用安全
            self._started = False
            self._loop = None
            self._thread = None
            self._pending = {}
            # ② 与 _runner 共用同一把锁：尚未开始的提交标记为丢弃，它们在循环取到之前不再执行
            for _future, submission in pending:
                if not submission.started:
                    submission.discarded = True

        if loop is None and thread is None:
            return

        deadline = None if timeout is None else time.monotonic() + timeout
        # ③ 在界内等待在飞提交完成（总预算语义，同 ThreadPoolModel._join_threads）
        if wait:
            self._wait_futures([future for future, _ in pending], deadline)
        # ④ 停止并回收循环
        self._stop_loop(loop, thread, deadline)

    @staticmethod
    def _wait_futures(futures: list[Any], deadline: float | None) -> None:
        """在给定界内等待在飞提交完成。

        等待的是提交的完成信号（``concurrent.futures.Future``）；协程自身的成败由完成
        回调在结算侧处理，此处只等"跑完"，且单个提交的异常不影响继续等待其余。
        """
        for future in futures:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return
            with contextlib.suppress(Exception):
                future.result(remaining)

    @staticmethod
    def _stop_loop(
        loop: asyncio.AbstractEventLoop | None,
        thread: threading.Thread | None,
        deadline: float | None,
    ) -> None:
        """停止并回收常驻循环：请求停止 → join 循环线程 → 关循环。

        循环线程未在界内退出（例如某协程同步占住了循环线程）时不强行 ``close``——对仍在
        运行的 loop 调 ``close`` 会抛 ``RuntimeError``，也无助于回收一条已经卡死的线程。
        """
        if loop is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            if deadline is None:
                remaining = _LOOP_STOP_TIMEOUT
            else:
                remaining = max(deadline - time.monotonic(), _LOOP_STOP_GRACE)
            thread.join(remaining)
            if thread.is_alive():
                return
        loop.close()
