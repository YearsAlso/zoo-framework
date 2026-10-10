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

import queue
import threading
import time
from abc import ABC, abstractmethod

from zoo_framework.constant import WorkerConstant
from zoo_framework.utils import LogUtils

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

    def prepare_workers(self, workers) -> int:
        """Handle "worker count exceeds the pool size" according to the backpressure policy.

        Must be called **before** the pool is created - ``expand`` semantics
        require the widened size to be in effect when the pool is built.

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
        # queue: the size stays; the excess queues inside the pool
        return self.effective_pool_size

    def start(self, core) -> None:
        """Build the queue and fixed worker threads at the **current** effective size (sized by prepare_workers before start)."""
        if self._threads:
            return
        if self.effective_pool_size <= 0:
            # Aligned with the old ThreadPoolExecutor(max_workers<=0) error
            # behavior: an illegal size is refused on the spot; MUST NOT silently
            # build a zero-thread pool so that submit never finds a "started"
            # container
            raise ValueError(
                f"pool size must be positive, got {self.effective_pool_size} (config key worker:pool:size)"
            )
        self._tasks = queue.Queue()
        self._threads = [
            threading.Thread(
                target=self._worker_loop,
                args=(self._tasks,),
                name=f"zoo-worker-{index}",
                daemon=True,
            )
            for index in range(self.effective_pool_size)
        ]
        for thread in self._threads:
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
