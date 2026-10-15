"""常驻异步执行模型（issue #235）的回归测试.

对应 openspec/changes/async-resident-event-loop 的两份 delta spec：

- ``async-worker-runtime``：异步 Worker 的驱动路径 MUST 由执行模型决定；常驻事件循环
  的生命周期 MUST 由执行模型持有且停机 MUST 幂等。
- ``scheduler-model``：``event_loop`` 模型 MUST 只接纳协程 Worker 且 MUST NOT 声称终止
  仍在执行的协程。

覆盖 tasks.md 5.6 点名的五类验收：**循环复用**（整段运行期只创建一次循环，用可注入的
创建点计数验证）、**停机后不再接收新任务（在飞结果仍投递）**、**非协程 Worker 被显式
拒绝**、**超时只观测不声称终止**、**``Semaphore(max_concurrent)`` 真正生效**；另加
"``worker:mode`` 缺省行为零变化"与"停机丢弃未开始协程"两条硬性纪律用例。

断言有效性（``.claude/rules/assertion-integrity.md``）：被测对象普遍就地改写，故一律
在**调用时快照**（在回调里记录当次的字段值）而非对可变对象做事后断言；对"不打印/未投递"
这类否定断言，先证明肯定面（如先断言至少投递了已开始协程的结果，再断言条数）。
"""

import asyncio
import threading
import time

import pytest

from zoo_framework.constant import WaiterConstant
from zoo_framework.core.waiter import WaiterFactory
from zoo_framework.core.waiter.base_waiter import BaseWaiter
from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.core.waiter.scheduler_model import (
    CONCURRENCY_EVENT_LOOP,
    LOOP_THREAD_NAME,
    STOP_CANCEL_QUEUED,
    WORKER_KIND_ASYNC,
    EventLoopModel,
    ThreadPerTaskModel,
    ThreadPoolModel,
)
from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor
from zoo_framework.workers import BaseWorker
from zoo_framework.workers.async_worker import AsyncWorker


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.005) -> bool:
    """等待条件成立；超时返回最后一次判定结果."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _make_waiter(mode: str | None = None, pool_size: int = 4) -> BaseWaiter:
    """构造一个指定模型的调度器（绕过配置，直接注入模型参数）."""
    return BaseWaiter(model_name=mode, pool_size=pool_size)


@pytest.fixture
def collector():
    """订阅统一结果主题并收集结果（按投递顺序追加）."""
    reactor = WaiterResultReactor()
    reactor.worker_names = None
    received: list = []
    reactor.on_result = received.append
    EventReactorManager().bind_topic_reactor(WaiterConstant.WORKER_RESULT_TOPIC, reactor)
    yield received
    reactor.on_result = None


class _AsyncProbe(AsyncWorker):
    """记录调用次数的异步 Worker."""

    def __init__(self, name: str, fail: bool = False):
        super().__init__(name)
        self._props["delay_time"] = 0
        self.calls = 0
        self.fail = fail
        self.thread_names: list[str] = []

    async def async_execute(self, *args, **kwargs):
        self.calls += 1
        self.thread_names.append(threading.current_thread().name)
        if self.fail:
            raise RuntimeError("async-boom")
        return "async-result"


class _SyncProbe(BaseWorker):
    """不具备协程能力的同步 Worker（用于准入拒绝用例）."""

    def __init__(self, name: str):
        super().__init__({"is_loop": False, "name": name})

    def _execute(self):
        return "sync"


class _SleepProbe(AsyncWorker):
    """等待型异步 Worker：进入执行体后先 await 睡 ``sleep`` 秒，再返回并标记完成.

    ``is_loop`` 置真：超时熔断发生在调度轮次内，而 ``reap_timeout`` 只作用于仍在调度
    列表里的 Worker——一次性 Worker 首轮后即被移出，无法被判定超时。
    """

    def __init__(self, name: str, sleep: float, max_concurrent: int = 10):
        super().__init__(name)
        self._props["delay_time"] = 0
        self._props["is_loop"] = True
        self._sleep = sleep
        self._max_concurrent = max_concurrent
        self.entered = 0
        self.finished = 0

    async def async_execute(self, *args, **kwargs):
        self.entered += 1
        await asyncio.sleep(self._sleep)
        self.finished += 1
        return "ok"


class _LoopHogProbe(AsyncWorker):
    """测试装置：进入执行体后**同步**占住循环线程一段时间。

    这不是可上生产的写法——设计中 ④ 明令禁止同步阻塞进入循环线程；此处仅用于在
    确定性的时点上制造"后一个提交尚未开始"的状态，以便验证停机语义
    ``stop_dispatch_cancel_queued``（已开始不中断、尚未开始被丢弃）。
    """

    def __init__(self, name: str, block: float):
        super().__init__(name)
        self._props["delay_time"] = 0
        self._block = block
        self.body_runs = 0
        self.entered = threading.Event()

    async def async_execute(self, *args, **kwargs):
        self.entered.set()
        time.sleep(self._block)  # 同步占住循环线程（测试装置）
        self.body_runs += 1
        return "hog"


# =============================================================================
# 1 · 契约：六项声明、原语、停机语义、模式登记
# =============================================================================


class TestEventLoopContract:
    """scheduler-model: event_loop 模型 MUST 以显式接口声明其契约."""

    def test_contract_items_are_non_empty(self):
        """Scenario: 契约六项可程序化查询且非空."""
        contract = EventLoopModel().describe()
        for key, value in contract.items():
            assert value not in ("", None, [], ()), f"{key} 为空"

    def test_declares_event_loop_primitive_and_stop_semantics(self):
        desc = EventLoopModel().describe()
        assert desc["concurrency_primitive"] == CONCURRENCY_EVENT_LOOP
        assert desc["stop_semantics"] == STOP_CANCEL_QUEUED
        assert desc["supported_worker_kinds"] == [WORKER_KIND_ASYNC]

    def test_mode_is_registered_and_keeps_other_modes(self):
        modes = WaiterConstant.IMPLEMENTED_WORKER_MODES
        assert WaiterConstant.WORKER_MODE_EVENT_LOOP in modes
        assert WaiterConstant.WORKER_MODE_THREAD in modes
        assert WaiterConstant.WORKER_MODE_THREAD_POOL in modes

    def test_factory_and_waiter_select_the_model(self):
        """Scenario: 以 event_loop 为模型名可装配出对应模型."""
        assert isinstance(WaiterFactory.get_waiter("event_loop").model, EventLoopModel)
        assert isinstance(_make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP).model, EventLoopModel)


# =============================================================================
# 2 · 准入拒绝：非协程 Worker 被显式拒绝
# =============================================================================


class TestAdmissionRejectsNonCoroutine:
    """scheduler-model: 模型 MUST 只接纳协程 Worker，其余显式拒绝且不静默降级."""

    def test_call_workers_rejects_sync_worker_listing_models(self):
        """Scenario: 同步 Worker 被显式拒绝."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        with pytest.raises(ValueError) as exc:
            waiter.call_workers([_SyncProbe("Sync")])

        message = str(exc.value)
        assert CONCURRENCY_EVENT_LOOP in message, "拒绝信息未指出不兼容之处"
        assert WaiterConstant.WORKER_MODE_THREAD in message, "拒绝信息未列出可选模型 thread"
        assert WaiterConstant.WORKER_MODE_THREAD_POOL in message, (
            "拒绝信息未列出可选模型 thread_pool"
        )

    def test_runtime_add_worker_rejects_sync_worker(self):
        """运行期注册走同一套准入：被拒的 Worker MUST NOT 进入调度列表."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        waiter.call_workers([_AsyncProbe("Ok")])
        try:
            sync = _SyncProbe("SyncRuntime")
            with pytest.raises(ValueError):
                waiter.add_worker(sync)
            assert sync not in waiter.workers, "被拒的同步 Worker 被静默纳入调度列表"
        finally:
            waiter.shutdown(wait=False)

    def test_async_worker_is_accepted(self):
        """肯定面：协程 Worker 通过准入."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        async_worker = _AsyncProbe("AsyncOk")
        waiter.call_workers([async_worker])
        try:
            assert async_worker in waiter.workers
        finally:
            waiter.shutdown(wait=False)


# =============================================================================
# 3 · 循环复用：整段运行期只创建一次循环
# =============================================================================


class TestResidentLoopReuse:
    """async-worker-runtime: 常驻循环模型下不自建循环."""

    def test_loop_created_exactly_once_across_many_dispatches(self, monkeypatch):
        """Scenario: 常驻循环模型下不自建循环（对创建点打桩计数）."""
        created: list = []
        real_new_event_loop = asyncio.new_event_loop

        def counting_new_event_loop():
            created.append(1)
            return real_new_event_loop()

        monkeypatch.setattr(asyncio, "new_event_loop", counting_new_event_loop)

        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        workers = [_AsyncProbe(f"L{i}") for i in range(8)]
        waiter.call_workers(workers)
        try:
            assert len(created) == 1, "启动模型时未恰好创建一次常驻循环"
            for _ in range(5):
                waiter.execute_service()
            assert _wait_until(lambda: all(worker.calls == 1 for worker in workers)), (
                "异步执行体未被调用"
            )
            time.sleep(0.1)  # 给可能存在的"每次派发新建循环"留出暴露窗口
            assert len(created) == 1, f"整段运行期新建了 {len(created)} 次循环，而非一次"
        finally:
            waiter.shutdown(wait=False)

    def test_loop_thread_is_named_daemon_and_reclaimed(self):
        """常驻循环跑在独立守护线程上，停机后被回收."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        waiter.call_workers([_AsyncProbe("Named")])
        thread = waiter.model._thread
        assert thread is not None and thread.name == LOOP_THREAD_NAME
        assert thread.daemon is True, "常驻循环线程 MUST 为守护线程（不得阻止进程退出）"
        try:
            assert thread.is_alive()
        finally:
            waiter.shutdown(wait=True, timeout=3.0)
        assert not thread.is_alive(), "停机后循环线程仍在运行"
        assert waiter.model._thread is None and waiter.model._loop is None

    def test_dispatch_runs_on_the_loop_thread(self):
        """声明的并发原语与执行位置一致：执行体跑在常驻循环线程上."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        worker = _AsyncProbe("OnLoop")
        waiter.call_workers([worker])
        try:
            waiter.execute_service()
            assert _wait_until(lambda: worker.calls == 1)
            assert worker.thread_names == [LOOP_THREAD_NAME], (
                f"执行体未跑在常驻循环线程上：{worker.thread_names}"
            )
        finally:
            waiter.shutdown(wait=False)


# =============================================================================
# 4 · 停机：不再接收新任务、在飞结果仍投递、幂等
# =============================================================================


class TestShutdownSemantics:
    """async-worker-runtime: 停机 MUST 幂等；关闭后的循环 MUST NOT 再接收新任务."""

    def test_submit_after_shutdown_is_rejected(self):
        """Scenario: 停机后不再接收新任务."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        worker = _AsyncProbe("Late")
        waiter.call_workers([worker])
        waiter.shutdown(wait=False)

        with pytest.raises(RuntimeError, match="not started"):
            waiter.model.submit(waiter.core, worker)

    def test_shutdown_waits_inflight_and_delivers_result(self, collector):
        """Scenario: 停机前在飞协程仍被结算（结果照常投递）."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        worker = _SleepProbe("InFlight", sleep=0.2)
        waiter.call_workers([worker])
        waiter.execute_service()
        assert _wait_until(lambda: worker.entered == 1), "在飞协程未开始"

        waiter.shutdown(wait=True, timeout=3.0)

        assert len(collector) == 1, "停机前的在飞结果未被投递"
        assert collector[0].content == "ok"
        assert collector[0].worker_name == worker.name
        assert waiter.core.worker_props == {}, "停机后在飞表残留"

    def test_shutdown_is_repeatable(self):
        """Scenario: 重复停机安全."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        waiter.call_workers([_AsyncProbe("Idem")])
        waiter.shutdown(wait=False)
        waiter.shutdown(wait=False)  # MUST NOT 抛异常
        assert waiter.model._started is False
        assert waiter.model._loop is None

    def test_model_teardown_is_idempotent(self):
        """模型层 teardown 自身 MUST 可重复调用（两层幂等中的模型层）."""
        model = EventLoopModel()
        core = WorkerDispatchCore()
        model.start(core)
        model.teardown(core, wait=False)
        model.teardown(core, wait=False)  # MUST NOT 抛异常
        assert model._started is False

    def test_start_after_teardown_rebuilds_the_loop(self):
        """停机后可重新启动（容器生命周期归模型，与池模型同形）."""
        model = EventLoopModel()
        core = WorkerDispatchCore()
        model.start(core)
        model.teardown(core, wait=False)
        model.start(core)
        try:
            worker = _AsyncProbe("Restart")
            core.begin(worker, None)
            model.submit(core, worker)
            assert _wait_until(lambda: worker.calls == 1)
        finally:
            model.teardown(core, wait=False)


# =============================================================================
# 5 · 停机丢弃未开始协程（stop_dispatch_cancel_queued）
# =============================================================================


class TestShutdownDiscardsNotStarted:
    """scheduler-model: 停机丢弃未开始的协程而不中断已开始的."""

    def test_started_not_interrupted_and_not_started_discarded(self, collector):
        """Scenario: 停机丢弃未开始的协程而不中断已开始的."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        hog = _LoopHogProbe("Hog", block=0.3)
        queued = _AsyncProbe("Queued")
        waiter.call_workers([hog, queued])
        waiter.execute_service()  # 同轮派发两者；hog 先跑并同步占住循环线程
        assert hog.entered.wait(2), "占住循环的协程未开始"

        # 此刻循环线程被 hog 同步占住：queued 的启动回调还在队列里，尚未开始执行
        waiter.shutdown(wait=True, timeout=3.0)

        assert hog.body_runs == 1, "已开始的协程被中断"
        assert queued.calls == 0, "尚未开始的协程在执行体层面被执行了"
        # 肯定面先行：已开始者恰好投递一条结果；再断言没有为被丢弃者伪造结果
        assert len(collector) == 1, f"结果条数异常：{[r.worker_name for r in collector]}"
        assert collector[0].worker_name == hog.name
        assert waiter.core.worker_props == {}, "停机后在飞表残留"


# =============================================================================
# 6 · 超时：只观测、不声称终止
# =============================================================================


class TestTimeoutObservation:
    """scheduler-model: 超时只记录、熔断、停止派发，MUST NOT 声称终止了协程."""

    def test_timeout_marks_unhealthy_without_terminating_the_coroutine(self):
        """Scenario: 超时不声称已终止."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        worker = _SleepProbe("Slow", sleep=0.4)
        worker._props["run_timeout"] = 0.05
        waiter.call_workers([worker])

        def tick_and_check():
            waiter.execute_service()
            return worker.name in waiter.core.broken

        try:
            assert _wait_until(tick_and_check, timeout=3.0), "超期未被观测为熔断"
            assert worker.name in waiter.core.broken
            # 只观测、不终止：协程仍在跑并最终完成（系统并未真正中断它）
            waiter.shutdown(wait=True, timeout=3.0)
            assert worker.finished == 1, "被判定超时的协程被真正终止了（与诚实性承诺不符）"
        finally:
            waiter.shutdown(wait=False)


# =============================================================================
# 7 · Semaphore 真正生效
# =============================================================================


class TestSemaphoreConcurrency:
    """event_loop 模型下同一 Worker 可并发推进多个等待型调用."""

    def test_waits_overlap_when_capacity_allows(self):
        """N 个各 sleep 0.2s 的等待型调用总耗时落在 0.2s 量级，而非 N×0.2s."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        worker = _SleepProbe("Sem", sleep=0.2, max_concurrent=5)
        waiter.call_workers([worker])
        try:
            loop = waiter.model._loop
            futures = [
                asyncio.run_coroutine_threadsafe(worker._execute_async(), loop) for _ in range(5)
            ]
            started = time.monotonic()
            for future in futures:
                future.result(5)
            elapsed = time.monotonic() - started
            assert worker.entered == 5, "并发调用未全部进入执行体"
            assert elapsed < 0.6, f"等待型调用未并发推进（总耗时 {elapsed:.3f}s）"
        finally:
            waiter.shutdown(wait=False)

    def test_semaphore_limit_is_enforced(self):
        """对照面：``Semaphore(max_concurrent=1)`` 真正限流（否则并发断言形同虚设）."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        worker = _SleepProbe("Sem1", sleep=0.2, max_concurrent=1)
        waiter.call_workers([worker])
        try:
            loop = waiter.model._loop
            futures = [
                asyncio.run_coroutine_threadsafe(worker._execute_async(), loop) for _ in range(4)
            ]
            started = time.monotonic()
            for future in futures:
                future.result(5)
            elapsed = time.monotonic() - started
            assert elapsed >= 0.7, f"Semaphore(1) 未真正限流（总耗时 {elapsed:.3f}s）"
        finally:
            waiter.shutdown(wait=False)


# =============================================================================
# 8 · 缺省行为零变化
# =============================================================================


class TestDefaultModeUnchanged:
    """硬性纪律：不显式配置 ``worker:mode`` 时的行为与合入前逐项一致."""

    def test_pool_disabled_still_derives_thread(self, monkeypatch):
        from zoo_framework.params import WorkerParams

        monkeypatch.setattr(WorkerParams, "WORKER_MODE", "", raising=False)
        monkeypatch.setattr(WorkerParams, "WORKER_POOL_ENABLE", False, raising=False)
        waiter = BaseWaiter()
        assert waiter.worker_mode == WaiterConstant.WORKER_MODE_THREAD
        assert isinstance(waiter.model, ThreadPerTaskModel)

    def test_pool_enabled_still_derives_thread_pool(self, monkeypatch):
        from zoo_framework.params import WorkerParams

        monkeypatch.setattr(WorkerParams, "WORKER_MODE", "", raising=False)
        monkeypatch.setattr(WorkerParams, "WORKER_POOL_ENABLE", True, raising=False)
        waiter = BaseWaiter()
        assert waiter.worker_mode == WaiterConstant.WORKER_MODE_THREAD_POOL
        assert isinstance(waiter.model, ThreadPoolModel)

    def test_event_loop_is_opt_in_only(self, monkeypatch):
        from zoo_framework.params import WorkerParams

        monkeypatch.setattr(WorkerParams, "WORKER_MODE", "event_loop", raising=False)
        assert isinstance(BaseWaiter().model, EventLoopModel)

        monkeypatch.setattr(WorkerParams, "WORKER_MODE", "", raising=False)
        assert BaseWaiter().worker_mode != WaiterConstant.WORKER_MODE_EVENT_LOOP


# =============================================================================
# 9 · 结果契约缝合点（P3）：run() 与模型托管路径共用同一份契约
# =============================================================================


class TestResultContractSeam:
    """P3：``BaseWorker.build_result`` 是唯一的结果构造入口，两条路径共用."""

    def test_build_result_shapes(self):
        """成功与失败两种形态由同一入口产出，字段与 #228 语义一致."""
        worker = _AsyncProbe("Seam")
        ok = worker.build_result("value")
        assert ok.content == "value" and ok.error is None and ok.success is True
        assert ok.worker_name == worker.name and ok.registry_name == worker.registry_name

        bad = worker.build_result(None, ValueError("boom"))
        assert bad.content is None and bad.success is False
        assert bad.error == "ValueError: boom"

    def test_run_and_model_path_produce_equal_success_shape(self, collector):
        """同一次成功执行的两种驱动路径产出同形的结果（worker_name / cls_name / content）."""
        direct = _AsyncProbe("ShapeDirect")
        direct_result = direct.run()

        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        worker = _AsyncProbe("ShapeLoop")
        waiter.call_workers([worker])
        try:
            waiter.execute_service()
            assert _wait_until(lambda: len(collector) == 1)
        finally:
            waiter.shutdown(wait=True, timeout=3.0)

        via_model = collector[0]
        assert direct_result.content == via_model.content == "async-result"
        assert direct_result.cls_name == via_model.cls_name
        assert (direct_result.worker_name == "ShapeDirect_1") and (
            via_model.worker_name == worker.name
        )

    def test_event_loop_failure_reports_distinguishable_result(self, collector):
        """#228 在常驻循环路径同样成立：失败仍投递一条带 error 的结果."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        worker = _AsyncProbe("Fail", fail=True)
        waiter.call_workers([worker])
        try:
            waiter.execute_service()
            assert _wait_until(lambda: len(collector) == 1), "失败执行未投递结果"
            failure = collector[0]
            assert failure.error is not None and failure.success is False
            assert failure.error.startswith("RuntimeError:")
        finally:
            waiter.shutdown(wait=True, timeout=3.0)
