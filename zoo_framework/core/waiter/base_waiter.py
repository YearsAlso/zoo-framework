"""Scheduler base class.

Design points:

- **Model-agnostic correctness logic is NOT implemented in this class**; it
  lives in ``WorkerDispatchCore``: the single settlement path, timeout
  observation and circuit-breaking, shutdown reclamation, runtime registration.
- **Concurrency primitives and container lifecycle belong to the scheduling
  model** (``SchedulerModel``). This class only assembles the model from
  config, runs scheduling rounds, and delegates dispatch and shutdown to the
  model.
- **Registration precedes dispatch** (``core.begin`` before ``model.submit``).
  If tasks were submitted before registration, an instantly finishing task
  would deregister itself before the registration lands, leaving an in-flight
  record that is never cleared, so the Worker would never be dispatched again.
- **Timeout is "observe + circuit-break" only**. CPython cannot safely
  interrupt a running thread, so the system does not claim a timed-out Worker
  was terminated; it records, marks unhealthy and stops dispatching.
- **Shutdown is an explicit action**. Stop dispatching, let the model reclaim
  the container, clear the in-flight table - and it is repeatable.
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
    """The base waiter (scheduler).

    Attributes:
        worker_mode: the effective scheduling model name
        pool_enable: whether a resource pool is in use (derived from the model
            name)
        model: the assembled scheduling model
        core: the dispatch core
    """

    def __init__(
        self,
        model_name: str | None = None,
        pool_size: int | None = None,
        backpressure_policy: str | None = None,
    ):
        """Assemble the scheduler.

        Args:
            model_name: the scheduling model name (a ``worker:mode`` value);
                None means derived from config
            pool_size: the pool size; None takes ``worker:pool:size``
            backpressure_policy: the policy for undersized pools; None is
                derived from ``worker:runPolicy``

        Raises:
            NotImplementedError: the model name is not an implemented mode
            ValueError: the run policy is not recognized
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
        # An explicitly passed policy is validated as well: in thread mode this
        # parameter is meaningless to the model, but silently ignoring a wrong
        # value would quietly forfeit the configured intent - MUST NOT be
        # silently ignored
        self._validate_backpressure_policy(policy)

        self.model: SchedulerModel = self._build_model(self.worker_mode, size, policy)

        # Model-agnostic bookkeeping and correctness logic is owned entirely by
        # the core (single owner)
        self.core = WorkerDispatchCore(default_run_timeout=WorkerParams.WORKER_RUN_TIMEOUT)

        self.register_handler()

    # ------------------------------------------------------------------ assembly

    @staticmethod
    def _build_model(model_name: str, pool_size: int, backpressure_policy: str) -> SchedulerModel:
        """Assemble the concrete model by its name."""
        if model_name == WaiterConstant.WORKER_MODE_THREAD_POOL:
            return ThreadPoolModel(pool_size=pool_size, backpressure_policy=backpressure_policy)
        return ThreadPerTaskModel()

    @staticmethod
    def _resolve_backpressure_policy(policy: str) -> str:
        """Map legacy ``worker:runPolicy`` values onto backpressure policies.

        Raises:
            ValueError: the value is not recognized - MUST NOT silently fall
                back to some default policy
        """
        mapped = LEGACY_POLICY_TO_BACKPRESSURE.get(policy)
        if mapped is None:
            raise ValueError(
                f"unknown run policy {policy!r}; expected one of {list(LEGACY_POLICY_TO_BACKPRESSURE)}"
            )
        return mapped

    @staticmethod
    def _validate_backpressure_policy(policy: str) -> None:
        """Validate a backpressure policy value.

        Shares the same set of legal values as the config path; unknown values
        MUST be rejected explicitly with the legal alternatives listed and MUST
        NOT be silently ignored - even if the current model (e.g. the
        thread-per-task model) does not use the parameter.

        Raises:
            ValueError: the value is not recognized
        """
        allowed = sorted(set(LEGACY_POLICY_TO_BACKPRESSURE.values()))
        if policy not in allowed:
            raise ValueError(f"unknown backpressure policy {policy!r}; expected one of {allowed}")

    # ------------------------------------------------------------------ state view
    # The scheduling list and the in-flight table are owned by the core; only
    # **read-only** views are exposed here so the state is not stored twice.
    # To change the scheduling list use call_workers / add_worker - a direct
    # assignment would bypass the model's start and make submit refuse the
    # dispatch under its "submit before start" contract.

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
        """Check whether the dispatch mode is implemented.

        Unimplemented modes MUST be rejected explicitly and MUST NOT silently
        execute as some other mode.

        Args:
            mode: the dispatch mode name

        Returns:
            The validated mode name

        Raises:
            NotImplementedError: the mode is not implemented
        """
        if mode not in WaiterConstant.IMPLEMENTED_WORKER_MODES:
            raise NotImplementedError(
                f"dispatch mode {mode!r} is not implemented; implemented modes are "
                f"{list(WaiterConstant.IMPLEMENTED_WORKER_MODES)}"
            )
        return mode

    def get_worker_mode(self, pool_enable):
        """Get the Worker's mode.

        An explicitly configured ``worker:mode`` takes precedence; when unset it
        is derived from ``worker:pool:enable``. Unimplemented modes are
        rejected explicitly.

        Args:
            pool_enable: the pool switch

        Returns:
            (mode name, whether a pool is used)
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
        """Register the handler.

        Binds the result reactor to the unified result topic.
        ``bind_topic_reactor`` is idempotent, so constructing the scheduler
        repeatedly does not pile up duplicate reactors under the topic.
        """
        EventReactorManager().bind_topic_reactor(
            WaiterConstant.WORKER_RESULT_TOPIC, WaiterResultReactor()
        )

    # ------------------------------------------------------------------ muster & registration

    def call_workers(self, worker_list: list):
        """Muster the workers and start the model container honoring the backpressure policy.

        Args:
            worker_list: the Workers participating in scheduling
        """
        self.core.set_workers(worker_list)
        # The backpressure policy must take effect before the pool is built: the
        # expand policy widens the size, and widening after the build is void
        self.model.prepare_workers(self.core.workers)
        self.model.start(self.core)

    def add_worker(self, worker):
        """Admit a Worker newly registered at runtime into scheduling.

        The scheduling list is owned by the scheduler; being listed in a
        registry alone is not enough for the Worker to be dispatched.

        Args:
            worker: the Worker to add to scheduling
        """
        self.core.add_worker(worker)

    def __del__(self):
        # No cleanup that may raise during teardown: an exception out of __del__
        # would only be printed to stderr
        with contextlib.suppress(Exception):
            self.shutdown(wait=False)

    # ------------------------------------------------------------------ scheduling round

    def execute_service(self):
        """Execute one service round.

        Only Workers declared looping and not circuit-broken remain in the
        scheduling list after this round.
        """
        if self.core.stopped:
            return

        for worker in list(self.core.workers):
            # Ignore malformed scheduling entries directly; MUST NOT raise an
            # attribute error on them
            if worker is None:
                continue

            # Timeout evaluation precedes the in-flight check: a Worker judged
            # timed out is circuit-broken this round
            self.core.reap_timeout(worker)

            if self.core.is_broken(worker):
                continue

            # The in-flight check precedes period scheduling: period scheduling
            # has side effects (advancing the sequence); calling it on a Worker
            # still executing would consume this trigger without dispatching
            if self.core.is_inflight(worker):
                continue

            # Period scheduling: a periodic Worker not yet due is skipped this
            # round but stays in the scheduling list
            if not self.core.is_due(worker):
                continue

            self._dispatch_worker(worker)

        self.core.workers = self.core.retain_looping(self.core.workers)

    def _dispatch_worker(self, worker):
        """Dispatch the worker.

        Registration MUST precede dispatch, or an instantly finishing task
        would complete its deregistration before the registration lands.

        Args:
            worker: the Worker to dispatch
        """
        handle = self.core.begin(worker, self.core.resolve_run_timeout(worker))
        if handle is None:
            return

        try:
            self.model.submit(self.core, worker)
        except Exception as e:
            # A dispatch failure must not interrupt the whole round; clear the
            # registration so the next round can retry
            self.core.abort(worker)
            LogUtils.error(f"Worker {worker.name} failed to dispatch: {e}", self.__class__.__name__)

    # ------------------------------------------------------------------ shutdown

    def shutdown(self, wait: bool = True, timeout: float | None = None) -> None:
        """Shutdown: stop dispatching and let the model reclaim the container.

        MUST be repeatable.

        Args:
            wait: whether to wait for in-flight tasks to finish
            timeout: the waiting bound in seconds; None means unbounded
        """
        if not self.core.mark_stopped():
            return

        LogUtils.info("waiter shutting down", self.__class__.__name__)

        self.model.teardown(self.core, wait=wait, timeout=timeout)
        self.core.clear()
