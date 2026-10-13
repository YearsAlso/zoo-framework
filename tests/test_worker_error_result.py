"""issue #228 回归：Worker 抛错时 MUST 也产生一条可区分的结果事件.

修复前的行为：``BaseWorker.run()`` 在 ``_execute`` 抛异常时把异常向上抛，
``WorkerDispatchCore.settle`` 观察到 ``error`` 后只在日志里记一条就 ``return``
——结果主题上什么都没有。于是任何"靠结果主题判断任务是否跑完"的消费者
（``WaiterResultReactor`` 或自己的中继反应器）会把**已经失败**的 Worker 当成
**仍在执行**：它已不在调度表里，却永远等不到结果，调用方只能靠墙钟超时兜底。

修复后的契约（本文件的断言口径）：

1. 失败产生一条结果，且**投递到同一统一结果主题**（分工不在于换主题，而在于
   同主题上"完成"这件事对成功与失败都成立）；
2. 该结果 MUST 可区分：``error`` 非空、``success`` 为假，携带错误信息；
3. 失败 MUST NOT 以"成功空结果"的形态投递（即 ``error`` 为空、``content`` 为空
   的那种"看起来成功"的结果）；
4. 生命周期钩子（``_on_error`` / ``_on_done``）与既有语义一致，不因本修复丢失。
"""

from zoo_framework.constant import WaiterConstant
from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.reactor import EventReactor
from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.workers import BaseWorker
from zoo_framework.workers.worker_result import WorkerResult


class Boom(BaseWorker):
    """执行体抛异常的 Worker（issue #228 的最小复现形态）。"""

    def __init__(self, name="boom"):
        BaseWorker.__init__(self, {"is_loop": False, "name": name})

    def _execute(self):
        raise RuntimeError("boom")


class Ok(BaseWorker):
    """执行体正常返回的 Worker。"""

    def __init__(self, name="ok"):
        BaseWorker.__init__(self, {"is_loop": False, "name": name})

    def _execute(self):
        return {"fine": True}


class TestFailedRunProducesResult:
    """run() 在失败时返回带错误信息的结果，而非把失败留在异常里。"""

    def test_failed_run_returns_a_result_marked_as_failure(self):
        """失败：返回 WorkerResult，error 非空且携带原因，success 为假。"""
        result = Boom().run()

        assert isinstance(result, WorkerResult), (
            "失败必须产生一条结果（此前异常直接向上抛，结果主题上什么都没有）"
        )
        assert result.topic == WaiterConstant.WORKER_RESULT_TOPIC
        assert result.error is not None, "失败结果 MUST 携带错误信息以便区分「失败」与「还在跑」"
        assert "boom" in result.error and "RuntimeError" in result.error
        assert result.success is False

    def test_failed_result_is_not_a_success_shaped_empty_result(self):
        """失败 MUST NOT 以「成功空结果」的形态出现。"""
        result = Boom().run()

        is_success_shaped = result.error is None and result.success
        assert not is_success_shaped, "失败结果看起来与成功结果无法区分"
        assert result.content is None, "失败没有可投递的执行产出"

    def test_successful_run_carries_no_error(self):
        """成功：error 为空、success 为真，结果内容为执行体返回。"""
        result = Ok().run()

        assert result.error is None
        assert result.success is True
        assert result.content == {"fine": True}

    def test_failure_still_calls_error_and_done_hooks(self):
        """失败路径的 _on_error / _on_done 钩子 MUST 保持触发（生命周期语义不变）。"""
        seen = {}

        class Hooked(Boom):
            def _on_error(self):
                seen["error"] = seen.get("error", 0) + 1

            def _on_done(self):
                seen["done"] = seen.get("done", 0) + 1

        Hooked().run()

        assert seen.get("error") == 1
        assert seen.get("done") == 1

    def test_failure_does_not_call_destroy_result(self):
        """失败没有产出可销毁的结果，_destroy_result MUST NOT 被调用。"""
        seen = {}

        class Hooked(Boom):
            def _destroy_result(self, result):
                seen["destroyed"] = result

        Hooked().run()

        assert "destroyed" not in seen


class TestFailureResultReachesTheResultTopic:
    """经单一结算路径投递：订阅结果主题的消费者能收到失败结果。"""

    def _deliver(self, worker):
        """把一次执行走完「登记 → 执行 → 结算 → 投递」，返回收到的结果列表。"""
        delivered = []
        reactor = EventReactor("issue228-probe")
        # 回调收到的是 EventReactorReq，WorkerResult 在其 content 上
        reactor.set_event_callback(lambda req: delivered.append(req.content))
        EventReactorManager().bind_topic_reactor(WaiterConstant.WORKER_RESULT_TOPIC, reactor)

        core = WorkerDispatchCore()
        assert core.begin(worker, None) is not None
        core.run_and_settle(worker)
        return delivered

    def test_failed_worker_delivers_one_distinguishable_result(self):
        """失败的 Worker 在结果主题上留下恰好一条可区分的结果。"""
        delivered = self._deliver(Boom())

        assert len(delivered) == 1, (
            f"失败 Worker 应留下恰好一条结果，实际 {len(delivered)} 条（此前为 0 条：失败只写日志）"
        )
        failure = delivered[0]
        assert failure.worker_name == "boom_1"
        assert failure.error is not None and "boom" in failure.error
        assert failure.success is False

    def test_successful_worker_delivers_a_success_result(self):
        """对照：成功 Worker 的结果 error 为空，二者可在同一主题上区分。"""
        delivered = self._deliver(Ok())

        assert len(delivered) == 1
        assert delivered[0].error is None
        assert delivered[0].success is True

    def test_failed_worker_is_no_longer_left_in_flight(self):
        """结算语义不变：失败后登记项被清除，该 Worker 不会永远算「在跑」。"""
        worker = Boom()
        core = WorkerDispatchCore()
        core.begin(worker, None)
        core.run_and_settle(worker)

        assert core.is_inflight(worker) is False
