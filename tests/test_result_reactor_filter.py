"""issue #229 回归：WaiterResultReactor.worker_names 过滤器 MUST 按注册名匹配.

修复前：``accepts`` 用等值比较 ``result.worker_name in worker_names``，而结果里的
``worker_name`` 带实例序号后缀（注册名 ``ok`` → 结果 ``ok_1``）——过滤器按**不带
后缀的注册名**比对，两者永远对不上，于是按文档设置 ``worker_names`` 反而把
**所有**结果都挡掉（无异常、无日志，静默不匹配）。

本文件的断言口径：

1. 按注册名筛选 MUST 收到该 Worker 的结果（含任意实例序号）；
2. 筛选 MUST 仍是真过滤——其他 Worker 的结果进不来，且**不是**前缀匹配
   （``ok`` 不得匹配 ``ok2``）；
3. ``worker_names=None`` 仍表示全收；
4. 精确实例名（``ok_1``）仍被接受，向后兼容。
"""

from zoo_framework.constant import WaiterConstant
from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor
from zoo_framework.workers import BaseWorker


class Probe(BaseWorker):
    """按注册名产出一条成功结果的 Worker。"""

    def __init__(self, name):
        BaseWorker.__init__(self, {"is_loop": False, "name": name})

    def _execute(self):
        return {"from": self.registry_name}


def _result_of(name):
    """取一个真实 Worker 执行后的结果（worker_name 带实例序号）。"""
    return Probe(name).run()


class TestAcceptsByRegistrationName:
    def test_filter_matches_registration_name_despite_ordinal_suffix(self):
        """worker_names=['ok'] MUST 接住 ''ok_1'' 的结果（修复前恒不匹配）。"""
        reactor = WaiterResultReactor()
        reactor.worker_names = ["ok"]

        result = _result_of("ok")
        assert result.worker_name == "ok_1", "前提：结果名带实例序号"
        assert reactor.accepts(result) is True

    def test_filter_still_rejects_other_workers(self):
        """筛选 MUST 保持过滤：别的 Worker 的结果进不来。"""
        reactor = WaiterResultReactor()
        reactor.worker_names = ["ok"]

        assert reactor.accepts(_result_of("other")) is False

    def test_filter_is_not_a_prefix_match(self):
        """``ok`` MUST NOT 匹配 ``ok2``（前缀式匹配是过度放行）。"""
        reactor = WaiterResultReactor()
        reactor.worker_names = ["ok"]

        assert reactor.accepts(_result_of("ok2")) is False

    def test_none_filter_accepts_every_worker(self):
        """worker_names=None 仍表示全收。"""
        reactor = WaiterResultReactor()
        reactor.worker_names = None

        assert reactor.accepts(_result_of("anything")) is True

    def test_exact_instance_name_is_still_accepted(self):
        """精确实例名仍被接受（向后兼容既有绕法）。"""
        reactor = WaiterResultReactor()
        reactor.worker_names = ["ok_1"]

        assert reactor.accepts(_result_of("ok")) is True

    def test_multiple_names_select_only_the_listed_workers(self):
        """多名筛选：列表内的都收，列表外的不收。"""
        reactor = WaiterResultReactor()
        reactor.worker_names = ["ok", "second"]

        assert reactor.accepts(_result_of("ok")) is True
        assert reactor.accepts(_result_of("second")) is True
        assert reactor.accepts(_result_of("third")) is False


class TestFilterThroughTheResultTopic:
    """经统一结果主题的端到端筛选（过滤器是框架自带的可用入口）。"""

    @staticmethod
    def _deliver(names):
        """执行若干 Worker，返回 on_result 实际收到的 worker_name 列表。"""
        received: list = []

        reactor = WaiterResultReactor()
        reactor.worker_names = names
        reactor.on_result = lambda result: received.append(result.worker_name)
        from zoo_framework.reactor.event_reactor_manager import EventReactorManager

        EventReactorManager().bind_topic_reactor(WaiterConstant.WORKER_RESULT_TOPIC, reactor)

        core = WorkerDispatchCore()
        for name in ("ok", "other"):
            worker = Probe(name)
            assert core.begin(worker, None) is not None
            core.run_and_settle(worker)
        return received

    def test_only_the_filtered_worker_is_received(self):
        """按注册名筛选时只收到该 Worker 的结果。"""
        assert self._deliver(["ok"]) == ["ok_1"]

    def test_none_receives_every_result(self):
        """None 时两条结果都收到。"""
        assert sorted(self._deliver(None)) == ["ok_1", "other_1"]
