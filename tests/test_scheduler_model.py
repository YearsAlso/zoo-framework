"""scheduler-model-seam 的调度模型契约测试.

对应 openspec/changes/scheduler-model-seam/specs/ 下的两份 spec：

- `scheduler-model`：模型 MUST 以显式接口声明契约（六项可程序化查询）、
  MUST 暴露运行期可观测指标、声明的并发原语 MUST 与执行位置一致、
  模型 MUST NOT 重新实现内核逻辑、模型选择 MUST 不做静默降级

抖动已按 spec 修订改为**按 Worker** 观测（由内核提供），其用例在
`tests/test_execution_time.py`；本文件只覆盖模型自身的契约与策略。

`ThreadPoolModel` 的三种背压策略吸收了原 `SimpleWaiter` / `StableWaiter` /
`SafeWaiter` 的唯一差异，故此处同时覆盖第 2.4 项的语义。
"""

import threading
import time

import pytest

from zoo_framework.constant import WaiterConstant, WorkerConstant
from zoo_framework.core.waiter.base_waiter import BaseWaiter
from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.core.waiter.scheduler_model import (
    BACKPRESSURE_EXPAND,
    BACKPRESSURE_QUEUE,
    BACKPRESSURE_REJECT,
    CONCURRENCY_THREAD_PER_TASK,
    CONCURRENCY_THREAD_POOL,
    METRIC_COMPLETED,
    METRIC_INFLIGHT,
    METRIC_JITTER,
    METRIC_TIMEOUTS,
    TIME_SEMANTICS_EVENT_DRIVEN,
    TIME_SEMANTICS_PERIODIC,
    ThreadPerTaskModel,
    ThreadPoolModel,
)
from zoo_framework.workers import BaseWorker

CONTRACT_KEYS = (
    "concurrency_primitive",
    "supported_time_semantics",
    "backpressure_policy",
    "stop_semantics",
    "supported_worker_kinds",
    "observable_metrics",
)


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.005) -> bool:
    """等待条件成立；超时返回最后一次判定结果."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class _ProbeWorker(BaseWorker):
    """记录执行次数与执行线程."""

    def __init__(self, name):
        super().__init__({"is_loop": False, "name": name})
        self.runs = 0
        self.thread_ident = None
        self.thread_name = None

    def _execute(self):
        self.runs += 1
        self.thread_ident = threading.get_ident()
        self.thread_name = threading.current_thread().name
        return self.runs


def _dispatch(core, model, worker):
    """按生产路径派发：**登记先于派发**（与 BaseWaiter._dispatch_worker 同形）."""
    handle = core.begin(worker, core.resolve_run_timeout(worker))
    assert handle is not None, "登记失败：该 Worker 已在飞"
    model.submit(core, worker)


def _all_models():
    """两个初始模型的实例（用于参数化）."""
    return [ThreadPerTaskModel(), ThreadPoolModel(pool_size=2)]


class TestModelContract:
    """scheduler-model: 调度模型 MUST 以显式接口声明其契约."""

    @pytest.mark.parametrize("model", _all_models())
    def test_contract_has_six_non_empty_items(self, model):
        """Scenario: 模型契约可被程序化查询."""
        contract = model.describe()
        assert set(contract) == set(CONTRACT_KEYS)
        for key, value in contract.items():
            assert value not in ("", None, [], ()), f"{type(model).__name__} 的 {key} 为空"

    def test_thread_per_task_declares_its_primitive(self):
        assert ThreadPerTaskModel().describe()["concurrency_primitive"] == (
            CONCURRENCY_THREAD_PER_TASK
        )

    def test_thread_pool_declares_its_primitive(self):
        assert ThreadPoolModel(pool_size=2).describe()["concurrency_primitive"] == (
            CONCURRENCY_THREAD_POOL
        )

    @pytest.mark.parametrize("model", _all_models())
    def test_supports_both_time_semantics(self, model):
        """模型声明的是**支持集合**，MUST NOT 把进程钉死在某一种时间语义上."""
        declared = set(model.describe()["supported_time_semantics"])
        assert {TIME_SEMANTICS_EVENT_DRIVEN, TIME_SEMANTICS_PERIODIC} <= declared

    @pytest.mark.parametrize("model_cls", [ThreadPerTaskModel, ThreadPoolModel])
    def test_models_do_not_reimplement_core_logic(self, model_cls):
        """模型 MUST NOT 重新实现结算收口、超时熔断、停机回收或派发登记."""
        forbidden = {"settle", "reap_timeout", "resolve_run_timeout", "begin", "attach_container"}
        assert forbidden.isdisjoint(dir(model_cls)), f"{model_cls.__name__} 重新实现了内核逻辑"


class TestDeclaredPrimitiveMatchesExecution:
    """scheduler-model: 声明的并发原语 MUST 与执行位置一致."""

    def test_thread_per_task_runs_off_caller_thread(self):
        """Scenario: 声明的并发原语与执行位置一致."""
        core = WorkerDispatchCore()
        worker = _ProbeWorker("probe-thread")
        model = ThreadPerTaskModel()
        model.start(core)
        core.set_workers([worker])

        _dispatch(core, model, worker)

        assert _wait_until(lambda: worker.runs == 1)
        assert worker.thread_ident != threading.get_ident(), "执行体跑在调用方线程上"

    def test_thread_pool_runs_off_caller_thread(self):
        core = WorkerDispatchCore()
        worker = _ProbeWorker("probe-pool")
        model = ThreadPoolModel(pool_size=2)
        model.start(core)
        core.set_workers([worker])
        try:
            _dispatch(core, model, worker)
            assert _wait_until(lambda: worker.runs == 1)
            assert worker.thread_ident != threading.get_ident(), "执行体跑在调用方线程上"
        finally:
            model.teardown(core, wait=False)


class TestModelMetrics:
    """scheduler-model: 模型 MUST 暴露运行期可观测指标."""

    def test_completion_is_counted_and_inflight_cleared(self):
        """Scenario: 运行期可查询在飞与完成数."""
        core = WorkerDispatchCore()
        worker = _ProbeWorker("metric")
        model = ThreadPerTaskModel()
        model.start(core)
        core.set_workers([worker])

        _dispatch(core, model, worker)

        assert _wait_until(lambda: core.metrics()[METRIC_COMPLETED] == 1), "完成数未被计数"
        assert core.metrics()[METRIC_INFLIGHT] == 0, "在飞数未在结算后清零"

    @pytest.mark.parametrize("model", _all_models())
    def test_declares_at_least_four_metrics_including_jitter(self, model):
        """Scenario: 模型 MUST 暴露至少四项指标（含触发抖动）."""
        declared = set(model.describe()["observable_metrics"])
        assert {METRIC_INFLIGHT, METRIC_COMPLETED, METRIC_TIMEOUTS, METRIC_JITTER} <= declared

    def test_metrics_are_available_while_running(self):
        """Scenario: 指标 MUST NOT 只在停机时可得."""
        core = WorkerDispatchCore()
        assert core.metrics()["completed"] == 0

        worker = _ProbeWorker("metric-running")
        model = ThreadPerTaskModel()
        model.start(core)
        core.set_workers([worker])
        _dispatch(core, model, worker)

        # 运行期即可查询（不依赖停机）
        assert set(core.metrics()) == {METRIC_INFLIGHT, METRIC_COMPLETED, METRIC_TIMEOUTS}


class TestPoolBackpressurePolicy:
    """scheduler-model: 池尺寸不足时的三种策略（吸收原 simple/stable/safe 的差异）."""

    def test_reject_raises_and_names_the_alternatives(self):
        model = ThreadPoolModel(pool_size=1, backpressure_policy=BACKPRESSURE_REJECT)
        workers = [_ProbeWorker("A"), _ProbeWorker("B")]

        with pytest.raises(ValueError) as exc:
            model.prepare_workers(workers)

        message = str(exc.value)
        assert "worker:pool:size" in message
        assert BACKPRESSURE_EXPAND in message and BACKPRESSURE_QUEUE in message

    def test_expand_widens_effective_size_without_rewriting_configured_size(self):
        model = ThreadPoolModel(pool_size=1, backpressure_policy=BACKPRESSURE_EXPAND)
        workers = [_ProbeWorker(f"E{i}") for i in range(3)]

        assert model.prepare_workers(workers) == 4
        assert model.pool_size == 1, "调用方配置的池尺寸被改写"

    def test_queue_keeps_size_unchanged(self):
        model = ThreadPoolModel(pool_size=1, backpressure_policy=BACKPRESSURE_QUEUE)
        workers = [_ProbeWorker(f"Q{i}") for i in range(3)]

        assert model.prepare_workers(workers) == 1
        assert model.pool_size == 1

    @pytest.mark.parametrize(
        "policy", [BACKPRESSURE_EXPAND, BACKPRESSURE_QUEUE, BACKPRESSURE_REJECT]
    )
    def test_within_capacity_no_policy_takes_effect(self, policy):
        model = ThreadPoolModel(pool_size=4, backpressure_policy=policy)
        assert model.prepare_workers([_ProbeWorker("only")]) == 4
        assert model.pool_size == 4

    def test_unknown_policy_is_rejected(self):
        with pytest.raises(ValueError):
            ThreadPoolModel(pool_size=2, backpressure_policy="nope")


class TestPoolTeardown:
    """scheduler-model: 停机语义 — 回收容器且 MUST 可重复调用."""

    def test_submit_after_teardown_is_rejected(self):
        core = WorkerDispatchCore()
        model = ThreadPoolModel(pool_size=2)
        model.start(core)
        model.teardown(core, wait=False)

        with pytest.raises(RuntimeError, match="not started"):
            model.submit(core, _ProbeWorker("after-teardown"))

    def test_teardown_is_idempotent(self):
        core = WorkerDispatchCore()
        model = ThreadPoolModel(pool_size=2)
        model.start(core)
        model.teardown(core, wait=False)
        model.teardown(core, wait=False)  # MUST NOT 抛异常

    def test_start_after_teardown_rebuilds_the_pool(self):
        core = WorkerDispatchCore()
        model = ThreadPoolModel(pool_size=2)
        model.start(core)
        model.teardown(core, wait=False)
        model.start(core)

        worker = _ProbeWorker("restart")
        _dispatch(core, model, worker)
        try:
            assert _wait_until(lambda: worker.runs == 1)
        finally:
            model.teardown(core, wait=False)

    def test_teardown_with_timeout_waits_within_budget(self):
        """带数值超时的停机 MUST 在预算内返回.

        该路径此前未被覆盖：其余用例传 ``wait=False`` 或 ``timeout=None``，
        而 ``timeout`` 为数值时才会走到单调时钟的预算计算。
        """
        core = WorkerDispatchCore()
        model = ThreadPoolModel(pool_size=2)
        model.start(core)

        worker = _ProbeWorker("budget")
        _dispatch(core, model, worker)
        assert _wait_until(lambda: worker.runs == 1)

        started = time.monotonic()
        model.teardown(core, wait=True, timeout=5.0)
        assert time.monotonic() - started < 5.0


class TestNoSilentDegradation:
    """scheduler-model: 模型选择 MUST 显式且不做降级（第 5.2 项的三个入口）."""

    def test_unimplemented_primitive_is_rejected(self):
        """入口一：请求未实现的并发原语（进程）."""
        with pytest.raises(NotImplementedError) as exc:
            BaseWaiter(model_name=WaiterConstant.WORKER_MODE_PROCESS)

        assert WaiterConstant.WORKER_MODE_PROCESS in str(exc.value)

    @pytest.mark.parametrize("bad_name", ["nope", "thread_pool_", "stabel", "simple", "safe"])
    def test_unknown_or_legacy_name_is_rejected_listing_models(self, bad_name):
        """入口二：未知模型名与旧策略名都被拒绝，且信息里列出可选模型."""
        from zoo_framework.core.waiter.waiter_factory import WaiterFactory

        with pytest.raises(ValueError) as exc:
            WaiterFactory.get_waiter(bad_name)

        message = str(exc.value)
        for mode in WaiterConstant.IMPLEMENTED_WORKER_MODES:
            assert mode in message, f"拒绝信息未列出可选模型 {mode}"

    def test_legacy_policy_names_are_not_silently_mapped(self):
        """旧策略名 MUST NOT 被静默映射到某个模型——它们只是背压策略的来源."""
        from zoo_framework.core.waiter.waiter_factory import WaiterFactory

        for policy in WorkerConstant.IMPLEMENTED_RUN_POLICIES:
            with pytest.raises(ValueError):
                WaiterFactory.get_waiter(policy)

    @pytest.mark.parametrize(
        "mode", [WaiterConstant.WORKER_MODE_THREAD, WaiterConstant.WORKER_MODE_THREAD_POOL]
    )
    def test_unknown_backpressure_policy_is_rejected_in_both_modes(self, mode):
        """入口三：超出模型声明的参数取值被拒绝——**线程模式下同样不静默忽略**."""
        with pytest.raises(ValueError) as exc:
            BaseWaiter(model_name=mode, backpressure_policy="definitely-not-a-policy")

        assert "backpressure policy" in str(exc.value)

    def test_unknown_run_policy_config_is_rejected(self, monkeypatch):
        """配置里写错运行策略时，构造调度器 MUST 明确拒绝而非取默认."""
        from zoo_framework.params import WorkerParams

        monkeypatch.setattr(
            WorkerParams, "WORKER_RUN_POLICY", "definitely-not-a-policy", raising=False
        )
        with pytest.raises(ValueError):
            BaseWaiter()


class _RecordingWorker(_ProbeWorker):
    """记录全局执行顺序（构造给定的短 tag 依序追加进 order 列表）."""

    def __init__(self, name, order, gate=None):
        super().__init__(name)
        self._order = order
        self._gate = gate
        self.tag = name  # worker.name 属性会拼上序号后缀，顺序断言用短 tag

    def _execute(self):
        self._order.append(self.tag)  # 先登记"已开始"，再占住线程（gate）
        if self._gate is not None:
            self._gate.wait(10)
        return super()._execute()


class TestQueueBackedPool:
    """replace-pool-dispatch-queue（#47 P2）：queue.Queue + 固定线程的池语义."""

    def test_threads_are_fixed_and_named(self):
        core = WorkerDispatchCore()
        model = ThreadPoolModel(pool_size=3)
        model.start(core)
        try:
            assert len(model._threads) == 3
            assert all(t.name.startswith("zoo-worker-") for t in model._threads)
            assert all(t.daemon for t in model._threads)
        finally:
            model.teardown(core, wait=True, timeout=5.0)
        assert all(not t.is_alive() for t in model._threads)

    def test_single_worker_pool_preserves_fifo_order(self):
        """排队=FIFO：尺寸 1 的池串行消费，后进顺序与提交顺序一致."""
        core = WorkerDispatchCore()
        model = ThreadPoolModel(pool_size=1, backpressure_policy=BACKPRESSURE_QUEUE)
        model.start(core)
        order: list[str] = []
        gate = threading.Event()
        blocker = _RecordingWorker("blocker", order, gate=gate)
        try:
            core.begin(blocker, timeout=None)
            model.submit(core, blocker)
            # 等 blocker 真正占住唯一工作线程（先于 gate 放行被记入 order 之前卡住），
            # 否则后三项会被并发消费而无法证明排队顺序
            assert _wait_until(lambda: "blocker" in order), "blocker 未被唯一线程取走"
            pending = [_RecordingWorker(f"w{i}", order) for i in range(3)]
            for worker in pending:
                core.begin(worker, timeout=None)
                model.submit(core, worker)
            gate.set()
            assert _wait_until(lambda: len(order) == 4)
            expected = [w.tag for w in pending]
            names = [n for n in order if n != "blocker"]
            assert names == expected, f"乱序：{order}"
        finally:
            gate.set()
            model.teardown(core, wait=True, timeout=5.0)

    def test_teardown_discards_queued_tasks(self):
        """stop_semantics=cancel_queued：未开始的排队任务被丢弃，已开始的不被中断."""
        core = WorkerDispatchCore()
        model = ThreadPoolModel(pool_size=1, backpressure_policy=BACKPRESSURE_QUEUE)
        model.start(core)
        order: list[str] = []
        gate = threading.Event()
        blocker = _RecordingWorker("blocker", order, gate=gate)
        queued = _RecordingWorker("queued", order)
        core.begin(blocker, timeout=None)
        model.submit(core, blocker)
        # 先确认 blocker 已开始（正在 gate 上阻塞），再投排队项：
        # "已开始不被中断"与"未开始被丢弃"才是各自成立
        assert _wait_until(lambda: "blocker" in order), "blocker 未被唯一线程取走"
        core.begin(queued, timeout=None)
        model.submit(core, queued)

        model.teardown(core, wait=False, timeout=None)
        gate.set()  # 放行已开始的任务
        time.sleep(0.3)

        assert order == ["blocker"], f"排队任务被丢弃后不应执行，已开始任务应跑完：{order}"

    def test_escaped_exception_is_logged_and_thread_survives(self, monkeypatch):
        """从执行单元逃逸的异常就地留痕；工作线程 MUST 存活继续服务."""
        import queue as queue_module

        import zoo_framework.core.waiter.scheduler_model as scheduler_module

        logged: list[str] = []

        class _CapturingLog:
            @staticmethod
            def error(message, *_args, **_kwargs):
                logged.append(str(message))

            @staticmethod
            def info(*args, **kwargs):
                pass

        monkeypatch.setattr(scheduler_module, "LogUtils", _CapturingLog)

        tasks: queue_module.Queue = queue_module.Queue()
        served: list[str] = []
        thread = threading.Thread(target=ThreadPoolModel._worker_loop, args=(tasks,), daemon=True)
        thread.start()
        try:

            def _boom(_worker):
                raise RuntimeError("escaped")

            tasks.put((_boom, object()))
            tasks.put((lambda _worker: served.append("alive"), object()))
            assert _wait_until(lambda: served == ["alive"]), "逃逸异常杀死了工作线程"
            assert any("escaped" in entry for entry in logged), "异常未留痕"
        finally:
            tasks.put(None)
            thread.join(2)

    def test_start_rejects_nonpositive_size(self):
        """尺寸非法当场拒绝（与旧 ThreadPoolExecutor(max_workers=0) 报错行为对齐）."""
        core = WorkerDispatchCore()
        model = ThreadPoolModel(pool_size=0)
        with pytest.raises(ValueError, match="pool size must be positive"):
            model.start(core)
