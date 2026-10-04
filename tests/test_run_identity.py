"""scheduler-model-seam 的 run-identity 组回归测试（第 4 组）.

对应 openspec/changes/scheduler-model-seam/specs/run-identity/spec.md：

- 4.1 两级标识的生成与唯一性
- 4.2 标识贯穿事件与 WorkerResult（显式字段，可据此筛选）
- 4.3 跨线程与跨调度模型传播；并发不串号
- 4.4 日志记录以结构化字段承载标识
- 4.5 状态作用域的归属可查
- 4.6 三处标识可相互对齐

状态用途例一律使用**进程内唯一的作用域名**，避免全局单例管理器在用例间串扰。
"""

import logging
import threading
import time
import uuid

import pytest

from zoo_framework.core.run_identity import RunIdentity, current_identity
from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.core.waiter.scheduler_model import ThreadPerTaskModel, ThreadPoolModel
from zoo_framework.fifo.node.event_fifo_node import EventNode
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker


def _unique_scope(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _model(kind: str):
    return ThreadPerTaskModel() if kind == "thread" else ThreadPoolModel(pool_size=2)


# =============================================================================
# 4.1 · 两级标识的生成
# =============================================================================


class TestIdentityGeneration:
    """run-identity: 系统 MUST 提供两级运行标识."""

    def test_identity_is_stable_within_a_run(self):
        """Scenario: 单次运行内标识唯一且不变."""
        identity = RunIdentity.start()
        with identity.bind():
            assert current_identity() is identity
            assert current_identity().run_id == identity.run_id
            assert current_identity() is identity  # 再次读取仍为同一标识

    def test_identity_is_unbound_by_default(self):
        assert current_identity() is None

    def test_different_runs_have_different_run_ids(self):
        """Scenario: 不同运行的标识不同."""
        first, second = RunIdentity.start(), RunIdentity.start()
        assert first.run_id != second.run_id
        assert first.session_id != second.session_id  # 未指定会话时各自开启新会话

    def test_same_session_can_host_multiple_runs(self):
        """Scenario: 会话可包含多次运行."""
        first = RunIdentity.start()
        second = RunIdentity.start(session_id=first.session_id)

        assert second.session_id == first.session_id
        assert second.run_id != first.run_id

    def test_binding_is_restored_after_exit(self):
        identity = RunIdentity.start()
        with identity.bind():
            pass
        assert current_identity() is None


# =============================================================================
# 4.2 · 标识贯穿事件与结果
# =============================================================================


class TestIdentityOnEvents:
    """run-identity: 标识 MUST 贯穿事件."""

    def test_event_carries_run_identity(self):
        """Scenario: 事件携带标识."""
        identity = RunIdentity.start()
        with identity.bind():
            node = EventNode(topic="t", content="c")

        assert node.run_id == identity.run_id
        assert node.session_id == identity.session_id

    def test_event_outside_a_run_has_no_identity(self):
        """未绑定运行标识时不编造值."""
        node = EventNode(topic="t", content="c")
        assert node.run_id is None
        assert node.session_id is None

    def test_event_identity_can_be_set_explicitly(self):
        node = EventNode(topic="t", content="c")
        node.set_identity("run-x", "sess-y")
        assert (node.run_id, node.session_id) == ("run-x", "sess-y")

    def test_events_can_be_filtered_by_run_id(self):
        """Scenario: 可据此筛选出属于该次运行的全部事件."""
        first, second = RunIdentity.start(), RunIdentity.start()
        nodes = []
        for identity in (first, second):
            with identity.bind():
                for index in range(3):
                    nodes.append(EventNode(topic=f"t{index}", content="c"))

        assert len([n for n in nodes if n.run_id == first.run_id]) == 3
        assert len([n for n in nodes if n.run_id == second.run_id]) == 3


# =============================================================================
# 4.3 · 跨线程与跨模型传播
# =============================================================================


class TestIdentityAcrossThreads:
    """run-identity: 标识 MUST 跨越线程与调度模型传播."""

    @pytest.mark.parametrize("kind", ["thread", "thread_pool"])
    def test_worker_thread_sees_the_dispatchers_identity(self, kind):
        """Scenario: 工作线程内可访问标识."""
        captured = {}

        class Probe(BaseWorker):
            def __init__(self):
                super().__init__({"name": f"Probe{kind}", "is_loop": False})

            def _execute(self):
                identity = current_identity()
                captured["run_id"] = identity.run_id if identity is not None else None
                captured["thread"] = threading.get_ident()
                return "ok"

        core = WorkerDispatchCore()
        model = _model(kind)
        model.start(core)
        worker = Probe()
        identity = RunIdentity.start()

        try:
            with identity.bind():
                assert core.begin(worker, None) is not None
                model.submit(core, worker)

            assert _wait_until(lambda: "run_id" in captured), "工作线程未执行"
            assert captured["run_id"] == identity.run_id, "工作线程里运行标识丢失"
            assert captured["thread"] != threading.get_ident(), "执行体跑在调用方线程上"
        finally:
            model.teardown(core, wait=False)

    def test_concurrent_runs_do_not_cross_identities(self):
        """Scenario: 并发执行不串号.

        两次运行各自在自己的上下文里派发，再由栅栏让两个工作线程同时在飞；
        任何一次读取拿到对方的标识即为串号。
        """
        seen = {}
        barrier = threading.Barrier(2)

        class Probe(BaseWorker):
            def __init__(self, name):
                super().__init__({"name": name, "is_loop": False})

            def _execute(self):
                barrier.wait(timeout=5)  # 确保两次运行在时间上重叠
                identity = current_identity()
                seen[self.name] = identity.run_id if identity is not None else None
                return "ok"

        core = WorkerDispatchCore()
        model = ThreadPerTaskModel()
        model.start(core)
        first_worker, second_worker = Probe("First"), Probe("Second")
        first, second = RunIdentity.start(), RunIdentity.start()

        try:
            with first.bind():
                assert core.begin(first_worker, None) is not None
                model.submit(core, first_worker)
            with second.bind():
                assert core.begin(second_worker, None) is not None
                model.submit(core, second_worker)

            assert _wait_until(lambda: len(seen) == 2), "并发执行未完成"
            assert seen[first_worker.name] == first.run_id
            assert seen[second_worker.name] == second.run_id
        finally:
            model.teardown(core, wait=False)

    @pytest.mark.parametrize("kind", ["thread", "thread_pool"])
    def test_result_is_stamped_with_the_dispatching_run(self, kind):
        """结果由内核按**登记时**的标识盖章，不依赖工作线程的上下文."""
        from zoo_framework.constant import WaiterConstant
        from zoo_framework.reactor import EventReactor
        from zoo_framework.reactor.event_reactor_manager import EventReactorManager

        core = WorkerDispatchCore()
        model = _model(kind)
        model.start(core)
        worker = BaseWorker({"name": f"Res{kind}", "is_loop": False})
        identity = RunIdentity.start()
        delivered = []

        reactor = EventReactor(f"identity_probe_{kind}")
        reactor.set_event_callback(delivered.append)
        EventReactorManager().bind_topic_reactor(WaiterConstant.WORKER_RESULT_TOPIC, reactor)

        try:
            with identity.bind():
                assert core.begin(worker, None) is not None
                model.submit(core, worker)

            assert _wait_until(lambda: delivered), "结果未被投递"
            # 回调收到的是 EventReactorReq，WorkerResult 在其 content 上
            result = delivered[0].content
            assert result.run_id == identity.run_id
            assert result.session_id == identity.session_id
        finally:
            model.teardown(core, wait=False)

    def test_result_identity_survives_a_lost_thread_context(self):
        """兜底：登记项已被清理时退回当前上下文，而非编造值."""
        core = WorkerDispatchCore()
        worker = BaseWorker({"name": "Lost", "is_loop": False})
        core.begin(worker, None)
        core.abort(worker)  # 模拟登记被熔断清理

        result = type("R", (), {"run_id": None, "session_id": None})()
        core.settle(worker, result=result)
        assert result.run_id is None


# =============================================================================
# 4.4 · 日志的结构化字段
# =============================================================================


class TestIdentityInLogs:
    """run-identity: 标识 MUST 出现在日志记录的结构化字段上."""

    def test_log_records_carry_identity_fields(self, caplog):
        """Scenario: 日志携带结构化字段，可被程序化提取."""
        identity = RunIdentity.start()
        with identity.bind(), caplog.at_level(logging.INFO):
            LogUtils.info("aligned log line")

        tagged = [r for r in caplog.records if getattr(r, "run_id", None) == identity.run_id]
        assert tagged, "日志记录未携带运行标识"
        assert all(r.session_id == identity.session_id for r in tagged)

    def test_log_outside_a_run_carries_null_identity(self, caplog):
        """未绑定标识时字段为 None，MUST NOT 编造值."""
        with caplog.at_level(logging.INFO):
            LogUtils.info("unbound log line")

        record = caplog.records[-1]
        assert record.run_id is None
        assert record.session_id is None


# =============================================================================
# 4.5 · 状态作用域的归属
# =============================================================================


class TestScopeOwnership:
    """run-identity: 状态作用域的归属可查."""

    def test_scope_records_the_owning_session(self):
        """Scenario: 被某次运行改动过的作用域可查得其所属会话标识."""
        manager = StateMachineManager()
        scope = _unique_scope("own")
        identity = RunIdentity.start(session_id="session-of-owner")

        with identity.bind():
            manager.set_state(scope, "k", 1)

        assert manager.get_scope_session(scope) == "session-of-owner"

    def test_scope_records_the_owning_run(self):
        """归属标识含运行标识，"运行"这一侧同样可查."""
        manager = StateMachineManager()
        scope = _unique_scope("ownrun")
        identity = RunIdentity.start()

        with identity.bind():
            manager.set_state(scope, "k", 1)

        owner = manager.get_scope_identity(scope)
        assert owner is not None
        assert owner.run_id == identity.run_id

    def test_ownership_is_not_rewritten_by_later_writes(self):
        """归属由**首个**写入者确定，之后不再改写."""
        manager = StateMachineManager()
        scope = _unique_scope("first")
        first = RunIdentity.start(session_id="first-session")
        later = RunIdentity.start(session_id="later-session")

        with first.bind():
            manager.set_state(scope, "k", 1)
        with later.bind():
            manager.set_state(scope, "k", 2)

        assert manager.get_scope_session(scope) == "first-session"

    def test_unknown_scope_has_no_owner(self):
        assert StateMachineManager().get_scope_session(_unique_scope("absent")) is None

    def test_write_without_identity_leaves_no_owner(self):
        """未绑定标识的写入不产生归属，MUST NOT 编造."""
        manager = StateMachineManager()
        scope = _unique_scope("noid")
        manager.set_state(scope, "k", 1)

        assert manager.get_scope_session(scope) is None


# =============================================================================
# 4.6 · 三处标识可对齐
# =============================================================================


class TestIdentityAlignment:
    """run-identity: 事件、状态与日志三处的标识可相互对齐."""

    def test_event_state_and_log_share_one_run_id(self, caplog):
        """Scenario: 三处标识可相互对齐."""
        manager = StateMachineManager()
        scope = _unique_scope("align")
        identity = RunIdentity.start()

        with identity.bind(), caplog.at_level(logging.INFO):
            node = EventNode(topic="aligned", content="c")
            manager.set_state(scope, "k", 1)
            LogUtils.info("aligned")

        owner = manager.get_scope_identity(scope)
        log_records = [r for r in caplog.records if getattr(r, "run_id", None) is not None]

        assert node.run_id == identity.run_id, "事件侧标识不一致"
        assert owner is not None and owner.run_id == identity.run_id, "状态侧标识不一致"
        assert log_records and log_records[-1].run_id == identity.run_id, "日志侧标识不一致"
        # 会话这一侧同样三处一致
        assert node.session_id == identity.session_id
        assert manager.get_scope_session(scope) == identity.session_id
        assert log_records[-1].session_id == identity.session_id
