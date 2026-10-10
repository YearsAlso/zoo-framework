"""Dispatch core: model-agnostic bookkeeping and correctness logic.

Five kinds of logic MUST be owned by this core; new scheduling models MUST NOT
re-implement them:

1. **Single settlement path** (``settle``) - clears the in-flight record and
   reports the result on success. All concurrency primitives share this one
   path, so results are delivered under any of them.
2. **Timeout observation and circuit-breaking** (``reap_timeout``) - record
   only, mark unhealthy, stop dispatching. CPython cannot safely interrupt a
   running thread, so the system MUST NOT claim it terminated one.
3. **Shutdown resource reclamation** (the ``shutdown`` path) - stop
   dispatching, clear the in-flight table; reclaiming the concurrency container
   (e.g. a thread pool) is provided by the model via ``teardown``.
4. **Runtime registration** (``add_worker``) - the scheduling list is owned by
   this core; being listed in a registry alone is not enough for a Worker to be
   dispatched.
5. **Period scheduling** (``is_due`` / ``jitter`` / ``skipped_count``) - period
   and phase are **per-Worker** declarations, independent of the concurrency
   primitive; if each model implemented its own, the absolute sequence, skip
   semantics and jitter sampling would be implemented multiple times and
   inevitably diverge.

Holds a second model-agnostic **concurrency contract**: the in-flight table and
the broken set are guarded by a **single** ``threading.RLock`` (both are
accessed concurrently by the dispatch thread and completion callbacks), plus
runtime metric counters.

Time base: every interval quantity in this module MUST use ``time.monotonic()``
and MUST NOT mix in wall-clock time.
"""

import threading
import time

from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker

from ..run_identity import RunIdentity, current_identity

#: The "not applicable" marker for jitter. Workers without a declared period
#: have no periodic triggers and MUST NOT have 0 substituted - 0 would be read
#: as "observed zero jitter".
JITTER_NOT_APPLICABLE = "N/A"

#: The miss sentinel of the policy cache (#47 P1). MUST NOT reuse None for
#: this - None is itself a legal resolution result ("no period declared"),
#: and falsy values (0 / False / "") are valid config values too; the cache
#: check MUST be identity comparison, not truthiness.
_POLICY_MISS = object()


class WorkerDispatchCore:
    """Dispatch core.

    Attributes:
        workers: the list of Workers participating in scheduling
        worker_props: the in-flight table, worker name ->
            {worker, run_time, run_timeout, deadline, container}
        broken: the set of circuit-broken (timed-out) worker names
        stopped: the shutdown flag
        default_run_timeout: the global default timeout; ``<= 0`` disables
            timeout evaluation
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
        """Set the list of Workers participating in scheduling."""
        with self._lock:
            self.workers = list(worker_list)
            # 调度列表整体替换：旧列表的策略条目全部作废
            self._policy_cache.clear()

    def add_worker(self, worker) -> None:
        """Admit a Worker newly registered at runtime into scheduling.

        The scheduling list is owned by this core; being listed in a registry
        alone is not enough for the Worker to be dispatched.
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
        """Filter the Workers that stay in the scheduling list after this round.

        All three conditions must hold: non-empty, **not circuit-broken**, and
        declared looping. Broken Workers MUST be removed from the list, or they
        would be re-evaluated every round (and "broken means stop dispatching"
        would lose its meaning). One-shot Workers do not take part in the next
        round - "exactly once" here is a **scheduling-bookkeeping** semantic
        (the same task is never dispatched twice concurrently), not a delivery
        attempt semantic: delivery is at-least-once and a failed event callback
        is retried by EventReactor (consumers needing exactly-once bring their
        own idempotency; the framework does not build in idempotency keys).
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
        """Cache one resolution keyed by (worker name, property) (#47 P1).

        The hit test is sentinel identity: None / 0 / False / "" in the cache
        are all **valid results** and MUST NOT be re-resolved as misses or
        fallen through to defaults. The caller may already hold
        ``self._lock`` (the RLock is reentrant); this method reads/writes under
        the lock uniformly.
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
        """Invalidate all policy entries for one worker name (the caller holds the lock)."""
        stale = [k for k in self._policy_cache if k[0] == worker_name]
        for k in stale:
            del self._policy_cache[k]

    def resolve_period(self, worker):
        """Resolve the Worker's period: self-report -> per-name override -> global default.

        The result is cached per worker name (#47 P1) while the three-stage
        semantics are preserved item by item: falsy self-reported/override
        values (0 / False / "") still fall through to the next stage per the
        existing rules, and the cache MUST NOT change that.

        Returns:
            The period in seconds; None when undeclared (callers then treat the
            Worker as event-driven)
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
        """Resolve the Worker's phase offset: self-report -> per-name override -> global default.

        The result is cached per worker name (#47 P1). Phase is the classic
        falsy case: an explicit ``phase: 0`` in config is a valid value, so the
        cache check MUST be sentinel comparison rather than truthiness.

        Returns:
            The phase offset in seconds; 0.0 when undeclared
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
        """Whether the Worker is due at this moment.

        Periodic scheduling computes trigger times from a **monotonic-clock
        absolute sequence** (base + phase + n x period); it MUST NOT schedule as
        "last execution finish time + period", which drifts cumulatively each
        round.

        When one round of execution spans several theoretical trigger times,
        the missed rounds are **skipped** and the next trigger is the next
        future time on the sequence; catch-up runs MUST NOT happen (catch-up
        self-amplifies under sustained overload).

        The **scheduling base** is the moment of the Worker's **first due
        check** (the framework has no process-level scheduling epoch), so the
        first trigger lands at "first-check time + phase" and later theoretical
        times are "base + phase + n x period".

        Args:
            worker: the target Worker
            now: the current monotonic time; None takes ``time.monotonic()``
                (handy for test injection)

        Returns:
            Whether due; always True for Workers without a declared period
            (event-driven semantics)
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
        """Record a trigger's jitter summary (last / upper bound / sample count)."""
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
        """The Worker's cumulative count of skipped rounds."""
        with self._lock:
            return self._skipped.get(worker.name, 0)

    def jitter(self, worker) -> dict:
        """The Worker's trigger jitter summary.

        Workers without a declared period return the explicit "not applicable"
        marker and MUST NOT return 0.
        """
        with self._lock:
            summary = self._jitter.get(worker.name)

        if summary is None:
            return {
                "applicable": False,
                "jitter": JITTER_NOT_APPLICABLE,
                "reason": "no period declared; no periodic triggers, jitter not applicable",
            }
        return {"applicable": True, **summary}

    # ---------------------------------------------------------------- 派发登记

    def begin(self, worker, timeout, deadline: float | None = None) -> dict | None:
        """Register a Worker that is about to be dispatched.

        **Registration MUST precede dispatch**: if the task were submitted
        before the registration, an instantly finishing task would deregister
        itself before the registration lands, leaving an in-flight record that
        is never cleared, and the Worker would never be dispatched again.

        Args:
            worker: the target Worker
            timeout: the relative timeout in seconds
            deadline: an absolute deadline (monotonic-clock base); when given
                it takes precedence over ``timeout``

        Returns:
            The registration entry; None if already in flight (the caller MUST
            NOT dispatch)
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
        """Attach the container (thread or Future) carrying this Worker to its registration."""
        with self._lock:
            handle = self.worker_props.get(worker.name)
            if handle is not None:
                handle["container"] = container

    def abort(self, worker) -> None:
        """Roll back the registration: clear the entry on dispatch failure so the next round can retry."""
        with self._lock:
            self.worker_props.pop(worker.name, None)

    # ---------------------------------------------------------------- 结算收口

    def settle(self, worker, result=None, error=None) -> None:
        """The single completion settlement: deregister in-flight state and report the result on success.

        Deregistration MUST happen regardless of success; an exception raised by
        the reporting step itself MUST NOT affect deregistration.

        The run identity stamped on the result comes from the **registration
        entry** (not the current context) - settlement may happen on a worker
        thread whose context differs from dispatch time; the identity in the
        registration entry is the source of truth.

        Args:
            worker: the Worker that finished executing
            result: the execution result; None on failure
            error: the exception raised during execution; None on success
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
            LogUtils.error(
                f"Worker {worker.name} execution failed: {error}", self.__class__.__name__
            )
            return

        if result is None:
            return

        try:
            EventReactorManager().dispatch(result.topic, result)
        except Exception as e:
            LogUtils.error(
                f"Worker {worker.name} result reporting failed: {e}", self.__class__.__name__
            )

    def run_and_settle(self, worker) -> None:
        """Execute once on a worker thread and settle.

        This is the model- and primitive-independent execution unit: the
        dispatching side MUST wrap it with ``carry_context(core.run_and_settle)``
        before submitting, or the worker thread will not inherit the caller's
        context and the run identity will be silently lost at dispatch time.

        Args:
            worker: the Worker to execute
        """
        try:
            result = self.run_worker(worker)
        except Exception as e:
            self.settle(worker, error=e)
        else:
            self.settle(worker, result=result)

    # ---------------------------------------------------------------- 超时熔断

    def resolve_run_timeout(self, worker):
        """Resolve the Worker's run timeout: self-report -> per-name override -> global default.

        The result is cached per worker name (#47 P1); the global default comes
        from ``default_run_timeout``, which does not change after construction
        (changing it would require invalidating the cache in step; there is
        currently no such runtime entry point).

        Returns:
            The timeout in seconds; None when undeclared
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
        """Timeout evaluation and circuit-breaking.

        Observation and circuit-breaking only: record, mark unhealthy, stop
        dispatching. The system MUST NOT claim it terminated a still-running
        Worker - CPython cannot safely interrupt a running thread.

        One of the two deadline sources applies: the **absolute deadline** given
        at registration takes precedence; otherwise the relative timeout is
        used.

        Returns:
            Whether this evaluation found the Worker timed out
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
                reason = f"dispatch deadline exceeded (deadline {deadline:.3f}, now {now:.3f})"
            else:
                timeout = handle.get("run_timeout")
                if not timeout or timeout <= 0:
                    return False
                elapsed = now - handle.get("run_time", 0)
                if elapsed < timeout:
                    return False
                reason = f"execution exceeded {timeout}s (actual {elapsed:.3f}s)"

            self.broken.add(worker.name)
            self.worker_props.pop(worker.name, None)
            self._timeouts += 1

        LogUtils.error(
            f"Worker {worker.name} {reason}, marked unhealthy and dispatch stopped;"
            "the system does not force-terminate still-running workers",
            self.__class__.__name__,
        )
        return True

    # ---------------------------------------------------------------- 执行入口

    @staticmethod
    def run_worker(worker):
        """Execute one Worker.

        Returns:
            WorkerResult; None when the worker is not a valid BaseWorker
        """
        if not isinstance(worker, BaseWorker):
            return None

        return worker.run()

    # ---------------------------------------------------------------- 停机

    def mark_stopped(self) -> bool:
        """Set the stopped flag.

        Returns:
            Whether this call is the first shutdown (repeated calls return
            False)
        """
        with self._lock:
            already_stopped = self.stopped
            self.stopped = True
        return not already_stopped

    def clear(self) -> None:
        """Clear the scheduling list, the in-flight table and the period-scheduling state.

        Period scheduling is reset as well: after a shutdown a fresh start
        should establish a new base rather than reuse the old sequence.
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
        """Runtime metrics: in-flight count, cumulative completions, timeout circuit-breaks.

        MUST be queryable at runtime, MUST NOT be available only at shutdown.
        Jitter is **per-Worker** observation, queried via ``jitter(worker)``, so
        it is not aggregated here.
        """
        with self._lock:
            return {
                "inflight": len(self.worker_props),
                "completed": self._completed,
                "timeouts": self._timeouts,
            }
