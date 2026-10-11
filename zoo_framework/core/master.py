"""Master - the lifecycle entry point.

P2 optimization:
1. removed the redundant ``loop_interval`` parameter
2. uses the new WorkerRegistry
3. simplified config loading
4. improved SVM integration
"""

import asyncio
import threading
from typing import Any

from zoo_framework.utils import LogUtils
from zoo_framework.workers import EventWorker, StateMachineWorker

from .aop import config_funcs
from .params_factory import ParamsFactory
from .worker_registry import get_worker_registry


class SVMWorker:
    """SVM (State Vector Machine) Worker - per-worker health metrics."""

    def __init__(self, check_interval: float = 10):
        self._workers: dict[str, Any] = {}
        self._metrics: dict[str, dict] = {}
        self._policies: list[str] = []
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._check_interval = check_interval
        # A wakeable wait instead of sleep: otherwise shutdown waits out a full
        # check period, up to check_interval seconds
        self._stop_event = threading.Event()

    def register_worker(self, name: str, worker: Any) -> None:
        """Register a Worker to the SVM manager."""
        with self._lock:
            self._workers[name] = worker
            self._metrics[name] = {
                "execute_count": 0,
                "error_count": 0,
                "total_execute_time": 0.0,
                "last_execute_time": 0.0,
                "status": "running",
            }
            # 如实表述：指标输入链路未接通，健康报告恒为零——不声称监控已生效
            LogUtils.debug(
                f"SVM worker '{name}' registered"
                " (metrics input not wired; get_health_report() returns zeros)"
            )

    def unregister_worker(self, name: str) -> None:
        """Remove a Worker from the SVM manager."""
        with self._lock:
            self._workers.pop(name, None)
            self._metrics.pop(name, None)
            LogUtils.debug(f"SVM worker '{name}' unregistered (metrics input not wired)")

    def record_execute(self, name: str, duration: float, success: bool = True) -> None:
        """Record a Worker's execution metrics."""
        with self._lock:
            if name not in self._metrics:
                return

            metrics = self._metrics[name]
            metrics["execute_count"] += 1
            metrics["total_execute_time"] += duration
            metrics["last_execute_time"] = duration

            if not success:
                metrics["error_count"] += 1

    def get_worker_health(self, name: str) -> dict:
        """Get a Worker's health status."""
        with self._lock:
            if name not in self._metrics:
                return {"status": "unknown"}

            metrics = self._metrics[name]
            execute_count = metrics["execute_count"]
            error_count = metrics["error_count"]

            if execute_count == 0:
                health_score = 100
            else:
                error_rate = error_count / execute_count
                health_score = max(0, int((1 - error_rate) * 100))

            avg_time = metrics["total_execute_time"] / execute_count if execute_count > 0 else 0

            return {
                "status": metrics["status"],
                "health_score": health_score,
                "execute_count": execute_count,
                "error_count": error_count,
                "error_rate": error_count / execute_count if execute_count > 0 else 0,
                "avg_execute_time": avg_time,
                "last_execute_time": metrics["last_execute_time"],
            }

    def get_all_workers_health(self) -> dict[str, dict]:
        """Get the health status of all Workers."""
        with self._lock:
            return {name: self.get_worker_health(name) for name in self._workers}

    def start_monitoring(self) -> None:
        """Start the monitoring thread."""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, name="zoo-svm")
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        # 监控线程真实启动，但指标输入未接通——如实说明，不声称监控已生效
        LogUtils.debug(
            "SVM monitor thread started (metrics input not wired; health report stays zero)"
        )

    def stop_monitoring(self) -> None:
        """Stop the monitoring thread.

        Wakes the monitor loop via the event so shutdown does not wait out a
        full check period.
        """
        self._running = False
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        LogUtils.debug("SVM monitor thread stopped (metrics input not wired)")

    def _monitor_loop(self) -> None:
        """The monitoring loop."""
        while self._running:
            try:
                self._check_workers_health()
            except Exception as e:
                LogUtils.error(f"❌ SVM monitor error: {e}")

            # A wait that shutdown can wake
            if self._stop_event.wait(self._check_interval):
                break

    def _check_workers_health(self) -> None:
        """Check the health status of all Workers."""
        with self._lock:
            for name, metrics in self._metrics.items():
                execute_count = metrics["execute_count"]
                error_count = metrics["error_count"]

                if execute_count == 0:
                    continue

                error_rate = error_count / execute_count

                if error_rate > 0.5 and execute_count > 10:
                    metrics["status"] = "unhealthy"
                    LogUtils.warning(f"⚠️ Worker '{name}' is unhealthy")
                elif error_rate > 0.2 and execute_count > 10:
                    metrics["status"] = "warning"
                    LogUtils.warning(f"⚠️ Worker '{name}' has warnings")
                else:
                    metrics["status"] = "running"


class MasterConfig:
    """Master configuration.

    P2 optimization: config centralized here.
    """

    def __init__(
        self,
        config_path: str = "./config.json",
        enable_svm: bool = True,
        svm_check_interval: int = 10,
        auto_save_interval: int = 60,
    ):
        self.config_path = config_path
        self.enable_svm = enable_svm
        self.svm_check_interval = svm_check_interval
        self.auto_save_interval = auto_save_interval


class Master:
    """Master - the zoo keeper (lifecycle manager).

    P2 optimized version:
    - removed the redundant ``loop_interval`` parameter
    - manages Workers with WorkerRegistry
    - simplified config
    - integrated SVM monitoring

    Attributes:
        config: the Master configuration
        worker_registry: the Worker registry
        svm_worker: the SVM monitoring Worker
        waiter: the Waiter scheduler
    """

    def __init__(self, config: MasterConfig | None = None):
        """Initialize the Master.

        P2 optimization: simplified parameters via a config object.

        Args:
            config: the Master configuration; defaults when None
        """
        # P2 optimization: use a config object
        self.config = config or MasterConfig()

        # P2 optimization: use the new WorkerRegistry
        self.worker_registry = get_worker_registry()

        # Runtime handles of the scheduling main loop
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._shutdown_done = False

        # Load config
        ParamsFactory(self.config.config_path)

        # Sequential check (change aop-determinism / #51): the config has just
        # been read, but if any params class was first imported and resolved in
        # a generation that "never saw the config", its values are frozen at the
        # defaults - fail loudly and name them, rather than let the runtime run
        # with a config that looks normal but is all defaults.
        if ParamsFactory.generation() > 0:
            from .aop.params import stale_param_classes

            stale = stale_param_classes()
            if stale:
                raise RuntimeError(
                    f"these params classes were imported and resolved before the config was loaded; their values are frozen at the defaults:"
                    f"{stale}. Move the params modules' first import to where the config file is visible"
                    f"(the same working directory as Master), or load the config before resolving; note that"
                    f"the package root imports the built-in params modules immediately, so starting from a different directory is the likeliest way to hit this check."
                )

        self._load_config()

        # P2 优化：简化 Worker 注册
        self._register_default_workers()

        # SVM Worker 集成
        # svm_check_interval 此前是声明了但从未被读取的配置项，此处真正生效
        self.svm_worker = (
            SVMWorker(self.config.svm_check_interval) if self.config.enable_svm else None
        )
        if self.svm_worker:
            self._setup_svm()

        # 创建 Waiter
        self._create_waiter()

    def _load_config(self) -> None:
        """Load config: iterate and call the import-time @configure functions **without arguments**.

        Sealed once consumed (change aop-determinism / #51): after sealing, an
        ``@configure`` registration fails loudly because that registration
        would never be consumed here again - turning the historical silent
        no-op into an error.
        """
        from .aop.configure import seal_config_funcs

        for value in config_funcs.values():
            value()
        seal_config_funcs()

    def _register_default_workers(self) -> None:
        """Register the default Workers.

        P2 optimization: registered via WorkerRegistry.
        """
        # Lazily instantiate
        self.worker_registry.register_class(
            "StateMachineWorker",
            StateMachineWorker,
            metadata={"priority": 100, "tags": ["system", "persistence"]},
        )
        self.worker_registry.register_class(
            "EventWorker", EventWorker, metadata={"priority": 50, "tags": ["system", "event"]}
        )

    def _setup_svm(self) -> None:
        """Set up SVM monitoring."""
        # Null-check first - the other four uses of svm_worker in this file all
        # guard (226/306/381/399); only this one missed; with SVM disabled
        # svm_worker is None and this used to raise AttributeError directly.
        if not self.svm_worker:
            return

        # Register all Workers to SVM
        for name, worker in self.worker_registry.get_all_workers().items():
            self.svm_worker.register_worker(name, worker)

        # Start monitoring
        self.svm_worker.start_monitoring()
        LogUtils.debug(
            "SVM worker setup done (metrics input not wired; get_health_report() returns zeros)"
        )

    def _create_waiter(self) -> None:
        """Create the Waiter.

        The scheduler is assembled by the **scheduling model name** (the name
        comes from ``worker:mode``, derived from ``worker:pool:enable`` when
        unset); an unrecognized model name is rejected explicitly.
        """
        from zoo_framework.core.waiter import WaiterFactory

        self.waiter = WaiterFactory.get_waiter()

        # Hand the Workers to the Waiter
        self.waiter.call_workers(list(self.worker_registry.get_all_workers().values()))

    def change_waiter(self, waiter) -> None:
        """Change the Waiter.

        Args:
            waiter: the new Waiter instance
        """
        if self.waiter is not None:
            raise Exception("Waiter already exists, cannot change")
        # [Known defect] The next line is **unreachable**: __init__ always sets
        # self.waiter, so the guard above is always true and the assignment
        # never executes - change_waiter can never fulfill its job (and it has
        # zero call sites repo-wide, no documented promise). Whether to allow
        # replacement or keep the guard is an unresolved semantics question,
        # so we deliberately do not guess a fix (recorded in
        # openspec/changes/establish-type-gate/tasks.md 3.1); an anchored ignore
        # keeps the defect visible instead of silently fixing it away.
        self.waiter = waiter  # type: ignore[unreachable]

    def register_worker(self, name: str, worker_class: type, metadata: dict | None = None) -> None:
        """Register a Worker.

        P2 optimization: a concise registration interface.

        Args:
            name: the Worker name
            worker_class: the Worker class
            metadata: metadata
        """
        self.worker_registry.register_class(name, worker_class, metadata)

        # The scheduling list is held by the Waiter: registering in the registry
        # alone does not get the Worker dispatched - it must be added to
        # scheduling too, or a runtime-registered Worker would never execute.
        worker = self.worker_registry.get_worker(name)
        if worker is None:
            return

        self.waiter.add_worker(worker)

        # Register to SVM when SVM is enabled
        if self.svm_worker:
            self.svm_worker.register_worker(name, worker)

    async def perform(self) -> None:
        """The task main loop."""
        while True:
            self.waiter.execute_service()
            # P2 optimization: use the configured interval
            await asyncio.sleep(1)

    def run(self) -> None:
        """Run the Master."""
        try:
            LogUtils.info("🎪 Master started, zoo is open!")
            # Create the event loop explicitly: asyncio.get_event_loop() is
            # deprecated when no loop is running, and it would reuse the last
            # loop, making repeated Master starts interfere with each other.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop

            self._task = loop.create_task(self.perform())
            # An exception out of the scheduling task must be visible and stop
            # the main loop; otherwise run_forever() would keep spinning while
            # scheduling has long stopped - the process is alive but does
            # nothing.
            self._task.add_done_callback(self._on_schedule_task_done)

            loop.run_forever()
        except KeyboardInterrupt:
            LogUtils.info("🛑 Master stopping...")
        finally:
            self.shutdown()

    def _on_schedule_task_done(self, task: asyncio.Task) -> None:
        """The close-out when the scheduling main loop ends: exceptions visible, event loop stopped.

        Args:
            task: the scheduling task
        """
        if task.cancelled():
            return

        error = task.exception()
        if error is not None:
            LogUtils.error(f"scheduling main loop terminated with an exception: {error!r}")

        # call_soon_threadsafe so this callback can stop the loop safely no
        # matter which thread triggers it
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)

    def shutdown(self) -> None:
        """Shut the Master down gracefully.

        Order: stop scheduling first (no more dispatches) -> cancel the
        scheduling task -> stop the event loop -> stop monitoring ->
        unregister Workers (firing their destroy hooks; the state machine
        persists here). MUST be repeatable.
        """
        if self._shutdown_done:
            return
        self._shutdown_done = True

        LogUtils.info("🧹 Shutting down Master...")

        # Stop the scheduler first: no new Worker MUST be dispatched during
        # shutdown
        if getattr(self, "waiter", None) is not None:
            self.waiter.shutdown()

        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()

        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)

        # Stop SVM monitoring
        if self.svm_worker:
            self.svm_worker.stop_monitoring()

        # Unregister the registered Workers: WorkerRegistry.unregister fires
        # their destroy hooks; the state machine Worker's last persistence
        # happens here.
        registry = getattr(self, "worker_registry", None)
        if registry is not None:
            for name in list(registry.get_all_workers().keys()):
                registry.unregister(name)

        LogUtils.info("👋 Master stopped")

    def get_health_report(self) -> dict[str, dict]:
        """Get the health report.

        Returns:
            The health status of all Workers
        """
        if self.svm_worker:
            return self.svm_worker.get_all_workers_health()
        return {}

    def get_worker_stats(self, worker_name: str) -> dict | None:
        """Get a Worker's statistics.

        Args:
            worker_name: the Worker name

        Returns:
            A statistics dict
        """
        worker = self.worker_registry.get_worker(worker_name)
        if worker is None:
            return None

        metadata = self.worker_registry.get_metadata(worker_name) or {}
        health = self.svm_worker.get_worker_health(worker_name) if self.svm_worker else {}

        return {
            "name": worker_name,
            "type": type(worker).__name__,
            "metadata": metadata,
            "health": health,
        }


# Convenience function
def create_master(config_path: str = "./config.json", enable_svm: bool = True) -> Master:
    """Create a Master instance.

    P2 optimization: a concise creation interface.

    Args:
        config_path: the config file path
        enable_svm: whether to enable SVM monitoring

    Returns:
        A Master instance
    """
    config = MasterConfig(config_path=config_path, enable_svm=enable_svm)
    return Master(config)
