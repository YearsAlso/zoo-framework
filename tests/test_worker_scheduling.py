"""fix-worker-scheduling 的回归测试.

对应 openspec/changes/fix-worker-scheduling/specs/ 下的四份 spec：
每条用例映射到一个具体 scenario。用例按能力分组：

- 调度器派发与在飞管理、循环语义、超时熔断、停机、运行期注册、模式校验
- 异步 Worker 在调度体系中的运行语义
- 事件管道的可靠性与响应器注册幂等

所有用例 MUST 在任意单平台上可运行：涉及并发时序的地方通过显式等待而非固定
sleep 收敛，避免出现"只有某个平台的 CI 才会红"的覆盖缺口。
"""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from zoo_framework.constant import WaiterConstant, WorkerConstant
from zoo_framework.core.waiter import SafeWaiter, StableWaiter, WaiterFactory
from zoo_framework.core.waiter.base_waiter import BaseWaiter
from zoo_framework.event import EventChannel
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.fifo import EventFIFO
from zoo_framework.fifo.node import EventNode
from zoo_framework.reactor import EventReactor
from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor
from zoo_framework.workers import BaseWorker, WorkerResult
from zoo_framework.workers.async_worker import AsyncWorker, AsyncWorkerPool


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.005) -> bool:
    """等待条件成立；超时返回最后一次判定结果."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _tick_until(waiter, predicate, timeout: float = 2.0, interval: float = 0.01) -> bool:
    """持续触发调度轮次直到条件成立.

    超时判定发生在调度轮次内（与 Master.perform 的轮询模型一致），因此要让某个
    Worker 被判定超时，必须持续推进调度轮次，而不是只等墙上时钟。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        waiter.execute_service()
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _make_waiter(mode: str | None = None, pool_size: int = 4) -> BaseWaiter:
    """构造一个指定模式的调度器（绕过配置，直接设定模式）."""
    waiter = BaseWaiter()
    if mode is not None:
        waiter.worker_mode = mode
        waiter.pool_enable = mode == WaiterConstant.WORKER_MODE_THREAD_POOL
        waiter.pool_size = pool_size
        if waiter.pool_enable:
            waiter.resource_pool = ThreadPoolExecutor(max_workers=pool_size)
    return waiter


class _RecordingWorker(BaseWorker):
    """记录执行次数的测试 Worker.

    props 中的 ``sleep_func`` 被替换为空实现，使执行后的延迟等待不产生真实开销。
    """

    def __init__(
        self,
        name: str,
        is_loop: bool = False,
        run_timeout: float | None = None,
        duration: float = 0.0,
    ):
        props = {
            "name": name,
            "is_loop": is_loop,
            "delay_time": 0,
            "sleep_func": lambda _seconds: None,
        }
        if run_timeout is not None:
            props["run_timeout"] = run_timeout
        super().__init__(props)
        self.duration = duration
        self.runs = 0
        self.errors = 0
        self.destroyed = 0

    def _execute(self):
        self.runs += 1
        if self.duration:
            time.sleep(self.duration)
        return f"result-{self.name}"

    def _on_error(self):
        self.errors += 1

    def _destroy(self, result):
        self.destroyed += 1


class _FailingWorker(_RecordingWorker):
    """执行必然失败的 Worker."""

    def _execute(self):
        self.runs += 1
        raise RuntimeError("boom")


# =============================================================================
# 1 · 循环与单次语义
# =============================================================================


class TestExecutionMode:
    """worker-scheduling: 调度 MUST 使循环 Worker 持续执行、单次 Worker 恰好执行一次."""

    def test_loop_worker_runs_every_round(self):
        """Scenario: 瞬时完成的循环 Worker 跨多轮持续执行."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Loop", is_loop=True)
        waiter.call_workers([worker])

        for _ in range(5):
            waiter.execute_service()
            _wait_until(lambda: worker.runs == waiter.worker_props.get("x", None) or True, 0.05)
            time.sleep(0.02)

        assert _wait_until(lambda: worker.runs == 5), f"只执行了 {worker.runs} 次"
        waiter.shutdown()

    def test_single_shot_worker_runs_exactly_once(self):
        """Scenario: 声明单次的 Worker 只执行一次."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Once", is_loop=False)
        waiter.call_workers([worker])

        for _ in range(5):
            waiter.execute_service()
            time.sleep(0.05)

        assert worker.runs == 1, f"声明单次的 Worker 执行了 {worker.runs} 次"
        waiter.shutdown()

    def test_duration_does_not_change_loop_semantics(self):
        """Scenario: 执行耗时长短不改变循环语义.

        耗时只影响 Worker 被重新派发的频率，不影响它是否仍被视为循环 Worker——
        慢 Worker 依然留在调度列表中，不会因为"还没跑完"而被丢弃。
        """
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        slow = _RecordingWorker("Slow", is_loop=True, duration=0.08)
        fast = _RecordingWorker("Fast", is_loop=True)
        waiter.call_workers([slow, fast])

        for _ in range(4):
            waiter.execute_service()
            time.sleep(0.05)

        assert fast.runs == 4, f"快 Worker 执行了 {fast.runs} 次"
        assert slow.runs >= 2, f"慢 Worker 只执行了 {slow.runs} 次"
        assert slow in waiter.workers, "慢的循环 Worker 被移出了调度列表"
        assert fast in waiter.workers, "快的循环 Worker 被移出了调度列表"
        waiter.shutdown()

    def test_loop_flag_is_boolean_not_callable(self):
        """Scenario: 循环标志不是可调用对象."""
        assert BaseWorker({"is_loop": True}).is_loop is True
        assert BaseWorker({"is_loop": False}).is_loop is False
        assert BaseWorker({}).is_loop is False
        assert isinstance(BaseWorker({"is_loop": True}).is_loop, bool)

    def test_loop_flag_tracks_config_not_subclass_shadowing(self):
        """Scenario: 配置字典是唯一真源."""
        worker = _RecordingWorker("Cfg", is_loop=True)
        worker._props["is_loop"] = False
        assert worker.is_loop is False


# =============================================================================
# 2 · 在飞状态与派发时序
# =============================================================================


class TestInflightState:
    """worker-scheduling: Worker 的执行状态 MUST 由单一收口维护."""

    @pytest.mark.parametrize(
        "mode",
        [WaiterConstant.WORKER_MODE_THREAD, WaiterConstant.WORKER_MODE_THREAD_POOL],
    )
    def test_instant_worker_is_not_stalled(self, mode):
        """Scenario: 登记与派发之间无时序依赖（两种模式各验一次）.

        回归目标：提交后再登记的写法会让瞬时完成的任务在登记之前就完成注销，
        在在飞表中留下永不清除的记录，使该 Worker 此后再不被派发。
        """
        waiter = _make_waiter(mode)
        worker = _RecordingWorker("Instant", is_loop=True)
        waiter.call_workers([worker])

        for _ in range(5):
            waiter.execute_service()
            time.sleep(0.03)

        assert _wait_until(lambda: worker.runs == 5), (
            f"{mode} 模式下瞬时 Worker 只执行了 {worker.runs} 次（被卡死）"
        )
        waiter.shutdown()

    def test_state_cleared_after_completion(self):
        """Scenario: 执行结束后无残留."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Cleared", is_loop=True)
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _wait_until(lambda: worker.name not in waiter.worker_props)
        assert worker.name not in waiter.worker_props

    def test_state_cleared_after_error(self):
        """Scenario: 执行抛异常时仍被清除状态."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _FailingWorker("Boom", is_loop=True)
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _wait_until(lambda: worker.name not in waiter.worker_props)
        # 失败被记录，而不是伪装成空结果
        assert worker.errors == 1

    def test_long_running_worker_not_dispatched_twice(self):
        """Scenario: 长时间运行的 Worker 不被重复派发."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Long", is_loop=True, duration=0.3)
        waiter.call_workers([worker])

        for _ in range(4):
            waiter.execute_service()
            time.sleep(0.02)

        assert worker.runs == 1, f"在飞期间被重复派发了 {worker.runs} 次"
        waiter.shutdown()


# =============================================================================
# 3 · 超时熔断
# =============================================================================


class TestTimeout:
    """worker-scheduling: 超时 MUST 被观测并熔断，MUST NOT 声称已终止."""

    def test_no_timeout_leaves_long_task_alone(self):
        """Scenario: 未声明超时时长任务不被误伤."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("NoTimeout", is_loop=True, duration=0.15)
        waiter.call_workers([worker])

        waiter.execute_service()
        _wait_until(lambda: worker.runs == 1)
        time.sleep(0.2)

        assert waiter._broken == set(), "未声明超时的 Worker 被误判为超时"
        waiter.shutdown()

    def test_timeout_marks_worker_unhealthy(self):
        """Scenario: 声明超时后按声明熔断."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Hang", is_loop=True, run_timeout=0.05, duration=0.6)
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _tick_until(waiter, lambda: worker.name in waiter._broken), (
            "超时的 Worker 未被熔断"
        )
        waiter.shutdown()

    def test_timed_out_worker_is_not_dispatched_again(self):
        """Scenario: 超时的 Worker 不再被派发."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Hang2", is_loop=True, run_timeout=0.05, duration=0.6)
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _tick_until(waiter, lambda: worker.name in waiter._broken)
        assert worker not in waiter.workers, "熔断的 Worker 仍留在调度列表"

        runs_at_break = worker.runs
        for _ in range(5):
            waiter.execute_service()
            time.sleep(0.02)
        assert worker.runs == runs_at_break, "熔断后仍被派发"
        waiter.shutdown()

    def test_timeout_does_not_block_scheduling_round(self):
        """Scenario: 熔断不阻塞后续调度轮次."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        hang = _RecordingWorker("Hung", is_loop=True, run_timeout=0.05, duration=0.8)
        other = _RecordingWorker("Other", is_loop=True)
        waiter.call_workers([hang, other])
        waiter.execute_service()

        # 持续调度直到挂死的 Worker 熔断，记录单轮最坏耗时
        worst = 0.0
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and hang.name not in waiter._broken:
            started = time.monotonic()
            waiter.execute_service()
            worst = max(worst, time.monotonic() - started)
            time.sleep(0.01)

        assert hang.name in waiter._broken, "挂死的 Worker 未被熔断"
        assert other.runs > 1, "挂死的 Worker 阻断了其余 Worker 的调度"
        assert worst < 0.3, f"单轮调度被挂死的 Worker 拖慢到 {worst:.3f}s"
        waiter.shutdown()

    def test_timeout_does_not_claim_termination(self):
        """超时语义的边界：系统不声称已终止仍在执行的 Worker."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Still", is_loop=True, run_timeout=0.05, duration=0.4)
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _tick_until(waiter, lambda: worker.name in waiter._broken), (
            "Worker 未被判定为超时"
        )
        # 判定为超时之后，执行体本身仍然跑完且只跑了一次——说明系统没有强制终止它
        assert _wait_until(lambda: worker.runs == 1)
        time.sleep(0.45)
        assert worker.runs == 1, "超时的 Worker 被执行了多次"
        waiter.shutdown()


# =============================================================================
# 4 · 异常隔离
# =============================================================================


class TestErrorIsolation:
    """worker-scheduling: 单个 Worker 的异常 MUST NOT 中断调度."""

    def test_one_worker_error_does_not_stop_others(self):
        """Scenario: Worker 抛异常时其余 Worker 仍被调度."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        bad = _FailingWorker("Bad", is_loop=True)
        good = _RecordingWorker("Good", is_loop=True)
        waiter.call_workers([bad, good])

        for _ in range(3):
            waiter.execute_service()
            time.sleep(0.05)

        assert _wait_until(lambda: good.runs == 3), f"好 Worker 只跑了 {good.runs} 次"
        waiter.shutdown()

    def test_none_entry_is_ignored(self):
        """Scenario: 非法调度项被忽略而非抛出."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Alive", is_loop=True)
        waiter.workers = [None, worker]

        waiter.execute_service()
        assert _wait_until(lambda: worker.runs == 1)
        waiter.shutdown()


# =============================================================================
# 5 · 结果上报
# =============================================================================


class TestResultReporting:
    """worker-scheduling: Worker 结果 MUST 沿事件管道投递且可被按名过滤."""

    @pytest.fixture
    def collector(self):
        """订阅统一结果主题并收集结果."""
        reactor = WaiterResultReactor()
        reactor.worker_names = None
        received: list = []
        reactor.on_result = received.append
        EventReactorManager().bind_topic_reactor(
            WaiterConstant.WORKER_RESULT_TOPIC, reactor
        )
        yield received
        reactor.on_result = None

    @pytest.mark.parametrize(
        "mode",
        [WaiterConstant.WORKER_MODE_THREAD, WaiterConstant.WORKER_MODE_THREAD_POOL],
    )
    def test_result_reported_in_both_modes(self, collector, mode):
        """Scenario: 资源池模式与线程模式下结果都被投递."""
        waiter = _make_waiter(mode)
        worker = _RecordingWorker("Rep", is_loop=False)
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _wait_until(lambda: len(collector) == 1), (
            f"{mode} 模式下结果未被投递"
        )
        assert collector[0].content == "result-Rep_1"
        assert collector[0].worker_name == worker.name
        waiter.shutdown()

    def test_result_reported_exactly_once(self, collector):
        """Scenario: 同一次执行的结果恰好投递一次."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Once1", is_loop=False)
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _wait_until(lambda: len(collector) >= 1)
        time.sleep(0.2)
        assert len(collector) == 1, f"结果被投递了 {len(collector)} 次"
        waiter.shutdown()

    def test_result_filtered_by_worker_name(self, collector):
        """Scenario: 按 Worker 名筛选接收方."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        first = _RecordingWorker("Alpha", is_loop=False)
        second = _RecordingWorker("Beta", is_loop=False)
        waiter.call_workers([first, second])

        # 只接收 Alpha 的结果
        WaiterResultReactor().worker_names = [first.name]

        waiter.execute_service()
        assert _wait_until(lambda: len(collector) == 1)
        time.sleep(0.2)

        assert len(collector) == 1, f"筛选后仍收到 {len(collector)} 条结果"
        assert collector[0].worker_name == first.name
        waiter.shutdown()

    def test_failed_worker_does_not_report_a_result(self, collector):
        """执行失败的 Worker 不应上报一个空结果."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _FailingWorker("Failing", is_loop=False)
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _wait_until(lambda: worker.runs == 1)
        time.sleep(0.15)
        assert collector == [], "失败的执行上报了结果"
        waiter.shutdown()


# =============================================================================
# 6 · 停机
# =============================================================================


class TestShutdown:
    """worker-scheduling: 停机 MUST 回收调度资源."""

    def test_shutdown_stops_dispatch(self):
        """Scenario: 停机后不再派发."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Stop", is_loop=True)
        waiter.call_workers([worker])
        waiter.execute_service()
        assert _wait_until(lambda: worker.runs == 1)

        waiter.shutdown()
        runs_after_shutdown = worker.runs
        for _ in range(3):
            waiter.execute_service()
        assert worker.runs == runs_after_shutdown, "停机后仍在派发"

    def test_shutdown_reclaims_pool_threads(self):
        """Scenario: 停机后线程资源被回收."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        pool = waiter.resource_pool
        worker = _RecordingWorker("Reclaim", is_loop=True)
        waiter.call_workers([worker])
        waiter.execute_service()
        assert _wait_until(lambda: worker.runs == 1)

        threads = list(getattr(pool, "_threads", ()))
        assert threads, "资源池未创建工作线程"
        waiter.shutdown()
        assert all(not thread.is_alive() for thread in threads), "停机后工作线程仍在运行"

    def test_shutdown_triggers_destroy_hook(self):
        """Scenario: 停机触发销毁钩子."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _RecordingWorker("Destroy", is_loop=True)
        assert worker.destroyed == 0
        waiter.shutdown()
        # 调度器的停机入口本身不负责 Worker 销毁钩子（由注册表注销触发），
        # 此处只断言调用停机不抛异常；销毁钩子的触发由 Master 级用例覆盖。

    def test_shutdown_is_idempotent(self):
        """Scenario: 停机可重复调用."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        waiter.call_workers([_RecordingWorker("Idem", is_loop=True)])
        waiter.shutdown()
        waiter.shutdown()


# =============================================================================
# 7 · 模式与策略校验
# =============================================================================


class TestModeValidation:
    """worker-scheduling: 未实现的调度模式 MUST NOT 被静默降级."""

    def test_unknown_run_policy_is_rejected(self):
        """Scenario: 无法识别的运行策略被明确拒绝."""
        with pytest.raises(ValueError):
            WaiterFactory.get_waiter("stabel")

    @pytest.mark.parametrize(
        "policy",
        [
            WorkerConstant.RUN_POLICY_SIMPLE,
            WorkerConstant.RUN_POLICY_STABLE,
            WorkerConstant.RUN_POLICY_SAFE,
        ],
    )
    def test_known_policies_are_supported(self, policy):
        """已实现的三种策略均可构造."""
        assert WaiterFactory.get_waiter(policy) is not None

    def test_unimplemented_mode_is_rejected(self):
        """Scenario: 请求未实现的调度模式被明确拒绝."""
        with pytest.raises(NotImplementedError):
            BaseWaiter.validate_worker_mode(WaiterConstant.WORKER_MODE_PROCESS)

    def test_implemented_modes_pass_validation(self):
        for mode in WaiterConstant.IMPLEMENTED_WORKER_MODES:
            assert BaseWaiter.validate_worker_mode(mode) == mode

    def test_unimplemented_constants_are_annotated(self):
        """Scenario: 未实现的常量被显式标注."""
        import inspect

        import zoo_framework.constant.waiter_constant as waiter_constant
        import zoo_framework.constant.worker_constant as worker_constant

        assert WaiterConstant.WORKER_MODE_PROCESS not in WaiterConstant.IMPLEMENTED_WORKER_MODES
        assert WorkerConstant.RUN_MODE_PROCESS not in WorkerConstant.IMPLEMENTED_RUN_MODES
        assert "未实现" in inspect.getsource(waiter_constant)
        assert "未实现" in inspect.getsource(worker_constant)

    def test_safe_waiter_rejects_more_workers_than_pool_size(self):
        """SafeWaiter 超出资源池尺寸时拒绝，而不是静默扩容."""
        waiter = SafeWaiter()
        waiter.pool_size = 1
        with pytest.raises(ValueError):
            waiter.call_workers([_RecordingWorker("A"), _RecordingWorker("B")])

    def test_stable_waiter_keeps_configured_pool_size(self):
        waiter = StableWaiter()
        configured = waiter.pool_size
        waiter.call_workers([_RecordingWorker(f"W{i}") for i in range(configured + 3)])
        assert waiter.pool_size == configured


# =============================================================================
# 8 · 异步 Worker 与调度体系
# =============================================================================


class _AsyncProbe(AsyncWorker):
    """记录调用次数的异步 Worker."""

    def __init__(self, name: str | None = None, fail: bool = False):
        super().__init__(name)
        self._props["delay_time"] = 0
        self.calls = 0
        self.fail = fail

    async def async_execute(self, *args, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("async-boom")
        return "async-result"


class TestAsyncWorkerRuntime:
    """async-worker-runtime: 异步 Worker MUST 在调度路径上执行其异步执行体."""

    @pytest.mark.parametrize(
        "mode",
        [WaiterConstant.WORKER_MODE_THREAD, WaiterConstant.WORKER_MODE_THREAD_POOL],
    )
    def test_async_execute_runs_on_schedule_path(self, mode):
        """Scenario: 经调度执行后异步执行体被调用."""
        waiter = _make_waiter(mode)
        worker = _AsyncProbe("AsyncProbe")
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _wait_until(lambda: worker.calls == 1), (
            f"{mode} 模式下异步执行体未被调用（改前会占着线程空睡 delay_time）"
        )
        waiter.shutdown()

    def test_async_result_equals_coroutine_return(self):
        """Scenario: 执行结果等于异步执行体的返回值."""
        waiter = _make_waiter(WaiterConstant.WORKER_MODE_THREAD_POOL)
        worker = _AsyncProbe("AsyncResult")
        waiter.call_workers([worker])
        waiter.execute_service()

        assert _wait_until(lambda: worker.calls == 1)
        # 直接走 BaseWorker.run() 验证返回值契约
        result = worker.run()
        assert isinstance(result, WorkerResult)
        assert result.content == "async-result", "结果是空值而非协程返回值"
        waiter.shutdown()

    def test_async_failure_propagates(self):
        """Scenario: 同步入口可观测到异常."""
        worker = _AsyncProbe("AsyncFail", fail=True)
        with pytest.raises(RuntimeError):
            worker.execute()

    def test_background_exception_is_reraised(self):
        """Scenario: 后台执行的异常可被取回."""
        task = _AsyncProbe("AsyncBg", fail=True).run_in_background()
        assert _wait_until(task.done)
        with pytest.raises(RuntimeError):
            task.result()

    def test_background_thread_does_not_block_exit(self):
        """Scenario: 存在未完成的后台任务时进程仍可退出."""
        task = _AsyncProbe("AsyncDaemon").run_in_background()
        assert task._thread.daemon is True
        task.result()

    def test_pool_reusable_across_event_loops(self):
        """Scenario: 依次在两个事件循环中使用同一实例."""
        import asyncio

        worker = _AsyncProbe("AsyncMultiLoop")
        pool = AsyncWorkerPool(max_workers=2)

        first = asyncio.run(pool.submit(worker))
        second = asyncio.run(pool.submit(worker))

        assert first == second == "async-result"

    def test_abstract_worker_is_not_instantiable(self):
        """Scenario: 未实现异步执行体的类不可实例化."""
        with pytest.raises(TypeError):
            AsyncWorker("abstract")

        class Incomplete(AsyncWorker):
            pass

        with pytest.raises(TypeError):
            Incomplete("incomplete")

    def test_execute_rejected_inside_running_loop(self):
        """在事件循环内调用同步入口会被明确拒绝，而不是返回无人 await 的 Task."""
        import asyncio

        worker = _AsyncProbe("AsyncInLoop")

        async def call_inside_loop():
            worker.execute()

        with pytest.raises(RuntimeError):
            asyncio.run(call_inside_loop())


# =============================================================================
# 9 · 事件管道可靠性与注册幂等
# =============================================================================


class TestEventPipelineReliability:
    """event-dispatch: 取出的事件 MUST 有确定去向，MUST NOT 被静默丢弃."""

    def test_empty_pop_returns_none_and_is_handled(self):
        """Scenario: 队列在取出瞬间变空不导致异常."""
        channel = EventChannel("empty-probe")
        assert channel.pop_value() is None

        from zoo_framework.workers.event_worker import EventWorker

        # 取出为空时消费循环必须结束，而不是对 None 调用方法
        EventWorker()._execute()

    def test_event_without_reactor_goes_to_dead_letter(self):
        """Scenario: 无响应器的事件有确定去向."""
        # 必须经 EventChannelManager 取通道：它才会被登记进通道注册表，
        # 消费循环遍历的正是注册表里的通道
        channel = EventChannelManager().get_channel("dead-letter-probe")
        node = EventNode(topic="no.reactor", content="x")
        channel.push_event(node)

        from zoo_framework.workers.event_worker import EventWorker

        EventWorker()._execute()

        assert channel.size() == 0
        assert len(channel.get_dead_letters()) == 1, "无响应器的事件被静默丢弃"
        assert channel.get_dead_letters()[0].topic == "no.reactor"

    def test_event_with_retry_budget_is_requeued(self):
        """Scenario: 声明了剩余重试次数的事件被回队."""
        channel = EventChannelManager().get_channel("retry-probe")
        node = EventNode(topic="no.reactor.retry", content="x")
        node.set_retry_times(2)
        channel.push_event(node)

        from zoo_framework.workers.event_worker import EventWorker

        EventWorker()._execute()

        assert channel.size() == 1, "仍有重试额度的事件未被回队"
        assert channel.get_dead_letters() == []
        assert channel.get_top().get_retry_times() == 1

    def test_retry_budget_is_exhausted_then_dead_lettered(self):
        """Scenario: 重试额度耗尽后记入死信."""
        channel = EventChannelManager().get_channel("retry-exhaust-probe")
        node = EventNode(topic="no.reactor.exhaust", content="x")
        node.set_retry_times(1)
        channel.push_event(node)

        from zoo_framework.workers.event_worker import EventWorker

        worker = EventWorker()
        worker._execute()  # 第 1 次：回队，额度 1 -> 0
        worker._execute()  # 第 2 次：额度耗尽 -> 死信

        assert channel.size() == 0
        assert len(channel.get_dead_letters()) == 1

    def test_event_delivered_to_reactor_never_enters_dead_letter(self):
        """有响应器的事件被正常投递，不进入死信."""
        hits: list = []
        topic = "delivered.topic"
        channel_name = "delivered-probe"
        reactor = EventReactor("delivered")
        reactor.set_event_callback(lambda req: hits.append(req.topic))
        EventChannelManager().refresh_channel(channel_name, topic, reactor)
        channel = EventChannelManager().get_channel(channel_name)

        channel.dispatch(topic, "payload")

        from zoo_framework.workers.event_worker import EventWorker

        EventWorker()._execute()

        assert hits == [topic], "事件未投递到响应器"
        assert channel.get_dead_letters() == []
        assert channel.size() == 0

    def test_late_arriving_event_is_visible_after_push(self):
        """事件入队后消费循环能取到它（并发空档的下界）."""
        fifo = EventFIFO()
        fifo.dispatch("some.topic", "content", "probe-channel")
        assert fifo.size() == 1
        assert fifo.pop_value() is not None
        assert fifo.pop_value() is None


class TestReactorRegistrationIdempotency:
    """event-dispatch: 响应器注册 MUST 幂等."""

    def test_same_reactor_rebound_keeps_count(self):
        """Scenario: 同一对象重复注册不增加数量."""
        topic = "idem.topic"
        reactor = EventReactor("idem")
        manager = EventReactorManager()

        for _ in range(3):
            manager.bind_topic_reactor(topic, reactor)

        assert len(manager.reactor_map.get(topic)) == 1

    def test_rebound_does_not_rename(self):
        """Scenario: 重复注册不修改已注册对象的名称."""
        topic = "idem.name.topic"
        reactor = EventReactor("stable_name")
        manager = EventReactorManager()
        manager.bind_topic_reactor(topic, reactor)
        original = reactor.reactor_name

        manager.bind_topic_reactor(topic, reactor)

        assert reactor.reactor_name == original

    def test_repeated_master_shutdown_keeps_reactor_count(self):
        """Scenario: 多次构造框架不影响响应器集合."""
        from zoo_framework.core import Master

        for _ in range(3):
            Master().shutdown()

        reactors = EventReactorManager().reactor_map.get(WaiterConstant.WORKER_RESULT_TOPIC)
        assert len(reactors) == 1, f"结果主题下堆积了 {len(reactors)} 个响应器"


class TestChannelConstraint:
    """event-dispatch: 从某通道分发的事件 MUST NOT 触发仅监听其他通道的响应器."""

    def test_reactor_bound_to_other_channel_is_not_triggered(self):
        """Scenario: 声明监听其他通道的响应器不被触发."""
        hits: list = []
        topic = "channel.constraint.topic"
        reactor = EventReactor("business_only")
        reactor.set_event_callback(lambda req: hits.append(req.topic))

        EventChannelManager().refresh_channel("business", topic, reactor)

        EventReactorManager().dispatch(topic, "x")
        assert hits == [], "仅声明 business 通道的响应器被默认通道触发了"

    def test_reactor_triggered_on_its_own_channel(self):
        """Scenario: 声明监听的通道上事件正常送达."""
        hits: list = []
        topic = "channel.constraint.hit"
        reactor = EventReactor("business_only_2")
        reactor.set_event_callback(lambda req: hits.append(req.topic))

        EventChannelManager().refresh_channel("business", topic, reactor)

        EventReactorManager().dispatch(topic, "x", channel="business")
        assert hits == [topic], "声明监听的通道上事件未送达"


# =============================================================================
# 10 · Master 级停机、动态注册与调度任务异常
# =============================================================================


class TestMasterLifecycle:
    """worker-scheduling: 停机 MUST 回收调度资源；运行期注册 MUST 进入调度."""

    def test_shutdown_triggers_worker_destroy_hook(self):
        """Scenario: 停机触发销毁钩子."""
        from zoo_framework.core import Master

        master = Master()
        destroyed: list = []

        class DestructibleWorker(BaseWorker):
            def __init__(self):
                super().__init__({"name": "Destructible", "is_loop": False, "delay_time": 0})

            def _destroy(self, result):
                destroyed.append(1)

        master.register_worker("Destructible", DestructibleWorker)
        master.shutdown()

        assert destroyed == [1], "停机未触发已注册 Worker 的销毁钩子"

    def test_shutdown_persists_state_machine(self):
        """Scenario: 停机后状态机落盘（销毁钩子链路的可观测产物）."""
        import os
        import pickle

        from zoo_framework.core import Master
        from zoo_framework.params import StateMachineParams
        from zoo_framework.statemachine import StateMachineManager

        master = Master()
        StateMachineManager().set_state("ShutdownScope", "k", 42)
        master.shutdown()

        path = StateMachineParams.PICKLE_PATH
        assert os.path.exists(path), "停机后状态机未落盘"

        with open(path, "rb") as f:
            saved = pickle.load(f)

        assert "ShutdownScope" in saved, "落盘内容不含停机前的状态"

    def test_shutdown_is_idempotent(self):
        """Scenario: 停机可重复调用."""
        from zoo_framework.core import Master

        master = Master()
        master.shutdown()
        master.shutdown()

    def test_register_worker_after_start_is_scheduled(self):
        """Scenario: 注册后下一轮被调度."""
        from zoo_framework.core import Master

        worker_holder: dict = {}

        class LateWorker(_RecordingWorker):
            def __init__(self):
                super().__init__("LateRegistered", is_loop=False)
                worker_holder["instance"] = self

        master = Master()
        master.register_worker("LateRegistered", LateWorker)

        instance = worker_holder["instance"]
        assert instance in master.waiter.workers, "运行期注册的 Worker 未进入调度列表"

        master.waiter.execute_service()
        assert _wait_until(lambda: instance.runs == 1), "运行期注册的 Worker 未被执行"
        master.shutdown()

    def test_schedule_task_exception_stops_loop(self):
        """Scenario: 调度任务抛异常时记录并停止主循环，而非空转."""
        import asyncio

        from zoo_framework.core import Master

        master = Master()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        master._loop = loop

        async def failing_schedule():
            raise RuntimeError("worker 崩了")

        task = loop.create_task(failing_schedule())
        task.add_done_callback(master._on_schedule_task_done)

        # 兜底：若回调未能停止循环，本用例会在这里超时失败而不是挂死
        loop.call_later(2.0, loop.stop)
        started = time.monotonic()
        loop.run_forever()
        elapsed = time.monotonic() - started

        loop.close()
        asyncio.set_event_loop(None)

        assert elapsed < 1.0, "调度任务异常后主循环仍在空转"
        assert task.exception() is not None, "调度任务的异常被吞掉了"

    def test_run_does_not_use_deprecated_loop_lookup(self):
        """守卫：Master.run 不得调用已弃用的事件循环获取方式.

        asyncio.get_event_loop() 在无运行循环时已发出 DeprecationWarning，
        且会复用上一个循环，使重复启动的 Master 相互干扰。
        本用例检查真实的调用点而非字符串——注释里提到该方法名是允许的。
        """
        import ast
        import inspect
        import textwrap

        from zoo_framework.core import Master

        tree = ast.parse(textwrap.dedent(inspect.getsource(Master.run)))
        deprecated_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get_event_loop"
        ]

        assert deprecated_calls == [], "Master.run 仍在使用已弃用的事件循环获取方式"
