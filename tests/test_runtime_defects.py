"""fix-runtime-defects 的回归测试.

对应 openspec/changes/fix-runtime-defects/ 下的 spec：每条用例映射到具体 scenario。
用例分两类：

- 缺陷复现（先红）：在当前实现上失败，修复后转绿。
- 契约守护（本就绿）：修复前后都应通过，防止修复过程破坏既有语义。
"""

import asyncio
import itertools
import threading
import time

import pytest

from zoo_framework.core import Master
from zoo_framework.core.worker_registry import WorkerRegistry
from zoo_framework.event import EventChannel
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.fifo import EventFIFO
from zoo_framework.fifo.node import EventNode
from zoo_framework.reactor import EventReactor
from zoo_framework.reactor.event_priorities import EventPriorities
from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.reactor.event_retry_strategy import EventRetryStrategy
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.workers import BaseWorker
from zoo_framework.workers.async_worker import AsyncWorker

_counter = itertools.count()


def _uniq(prefix: str) -> str:
    """生成进程内唯一的名称，避免全局单例状态在用例间串扰."""
    return f"{prefix}_{next(_counter)}"


# =============================================================================
# A 组 · 入口可用性（worker-lifecycle / lock-primitives）
# =============================================================================


class TestFrameworkEntrypoint:
    """worker-lifecycle: 框架管理器 MUST 能以默认配置构造."""

    def test_master_constructs_with_default_config(self):
        """Scenario: 默认配置构造成功."""
        master = Master()
        assert master is not None
        master.shutdown()

    def test_master_registers_default_workers(self):
        """Scenario: 默认 Worker 注册后可被枚举."""
        master = Master()
        try:
            names = list(master.worker_registry.get_all_workers().keys())
            assert "StateMachineWorker" in names
            assert "EventWorker" in names
        finally:
            master.shutdown()

    def test_master_construction_is_repeatable(self):
        """Scenario: 构造过程可重复."""
        first = Master()
        second = Master()
        try:
            assert first is not second
        finally:
            first.shutdown()
            second.shutdown()


class TestWorkerRegistryContract:
    """worker-lifecycle: Worker 注册 MUST 接受可产出实例的 Worker 定义."""

    def test_register_class_then_get_instance(self):
        """Scenario: 注册 Worker 类并取用实例."""

        class DummyWorker(BaseWorker):
            def __init__(self):
                super().__init__({"name": _uniq("Dummy")})

        registry = WorkerRegistry()
        name = _uniq("Dummy")
        registry.register_class(name, DummyWorker)
        assert isinstance(registry.get_worker(name), DummyWorker)

    def test_repeated_get_returns_same_instance(self):
        """Scenario: 同一名称重复取用返回同一实例."""

        class CachedWorker(BaseWorker):
            def __init__(self):
                super().__init__({"name": _uniq("Cached")})

        registry = WorkerRegistry()
        name = _uniq("Cached")
        registry.register_class(name, CachedWorker)
        assert registry.get_worker(name) is registry.get_worker(name)

    def test_registration_does_not_instantiate_eagerly(self):
        """Scenario: 注册时不立即实例化."""

        class LazyWorker(BaseWorker):
            instances = 0

            def __init__(self):
                LazyWorker.instances += 1
                super().__init__({"name": _uniq("Lazy")})

        registry = WorkerRegistry()
        name = _uniq("Lazy")
        registry.register_class(name, LazyWorker)
        assert LazyWorker.instances == 0
        assert name in registry._worker_classes

    def test_rejects_non_worker_definition(self):
        """Scenario: 拒绝不可产出 Worker 的输入."""

        class NotAWorker:
            pass

        registry = WorkerRegistry()
        with pytest.raises(TypeError):
            registry.register_class(_uniq("NotAWorker"), NotAWorker)


class TestLockPrimitives:
    """lock-primitives: 包可导入、公开类型可用作上下文管理器、文档与行为一致."""

    def test_package_is_importable(self):
        """Scenario: 导入锁原语包."""
        import zoo_framework.lock  # noqa: F401

    def test_public_types_importable_from_package_root(self):
        """Scenario: 从包根导入公开类型."""
        from zoo_framework.lock import BaseLock, CountLock, TimeLock  # noqa: F401

    def test_public_types_instantiable(self):
        """Scenario: 公开类型可被实例化."""
        from zoo_framework.lock import BaseLock, CountLock, TimeLock

        assert BaseLock() is not None
        assert CountLock(count=2) is not None
        assert TimeLock(timeout=2) is not None

    @pytest.mark.parametrize("type_name", ["BaseLock", "CountLock", "TimeLock"])
    def test_context_manager_protocol(self, type_name):
        """Scenario: 以 with 语句正常进出."""
        import zoo_framework.lock as lock_module

        lock_type = getattr(lock_module, type_name)
        with lock_type():
            pass

    @pytest.mark.parametrize("type_name", ["BaseLock", "CountLock", "TimeLock"])
    def test_context_body_exception_propagates(self, type_name):
        """Scenario: 上下文体内的异常向外传播（不得被 __exit__ 吞掉）."""
        import zoo_framework.lock as lock_module

        lock_type = getattr(lock_module, type_name)
        with pytest.raises(RuntimeError, match="boom"), lock_type():
            raise RuntimeError("boom")

    def test_count_gate_admits_by_capacity(self):
        """Scenario: 按容量放行 —— 容量 N 时前 N 次成功，第 N+1 次失败."""
        from zoo_framework.lock import CountLock

        gate = CountLock(count=3)
        assert [gate.acquire() for _ in range(4)] == [True, True, True, False]

    def test_count_gate_release_returns_quota(self):
        """Scenario: 释放归还额度."""
        from zoo_framework.lock import CountLock

        gate = CountLock(count=1)
        assert gate.acquire() is True
        assert gate.acquire() is False
        gate.release()
        assert gate.acquire() is True

    def test_count_gate_types_share_admission_semantics(self):
        """Scenario: 计数型类型之间的放行语义一致."""
        from zoo_framework.lock import CountLock, TimeLock

        for gate in (CountLock(count=2), TimeLock(timeout=2)):
            assert [gate.acquire() for _ in range(3)] == [True, True, False]

    def test_lock_docstrings_do_not_promise_unimplemented_behaviour(self):
        """Scenario: 未提供超时语义的类型不得声明超时（文档与行为一致性核对）.

        只做机械可判定的部分：文档不得**承诺**超时/回调行为（允许以声明口吻
        说明该语义未实现）。完整一致性核对属 spec 所述的可显式验证范围。
        """
        from zoo_framework.lock import CountLock, TimeLock

        for lock_type in (CountLock, TimeLock):
            doc = lock_type.__doc__ or ""
            assert "超时后" not in doc, f"{lock_type.__name__} 承诺了未实现的超时语义"
            assert "触发回调" not in doc, f"{lock_type.__name__} 承诺了未实现的回调语义"


# =============================================================================
# B 组 · 事件系统（event-dispatch）
# =============================================================================


def _reactor(name: str, callback) -> EventReactor:
    reactor = EventReactor(name)
    reactor.set_event_callback(callback)
    return reactor


class TestRetryStrategies:
    """event-dispatch: 每种重试策略 MUST 实现其声明语义且 MUST 终止."""

    @staticmethod
    def _run_with_timeout(reactor, timeout=3.0):
        """在守护线程中执行，避免缺陷导致的死循环挂住整个测试会话."""
        done = threading.Event()

        def runner():
            reactor.execute("t", "c")
            done.set()

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return done.wait(timeout)

    def test_retry_once_stops_after_single_failure(self):
        """Scenario: 仅重试一次的策略在失败后终止."""
        calls = []

        def failing(req):
            calls.append(1)
            raise RuntimeError("fail")

        reactor = _reactor(_uniq("r"), failing)
        reactor.set_retry_strategy(EventRetryStrategy.RetryOnce, 1)
        assert self._run_with_timeout(reactor), "execute 未返回（疑似不终止）"
        assert len(calls) == 1

    def test_retry_never_stops_after_failure(self):
        """Scenario: 从不重试的策略在失败后立即终止（不得死循环）."""
        calls = []

        def failing(req):
            calls.append(1)
            time.sleep(0.001)  # 让出 CPU，避免缺陷版本空转占满核心
            raise RuntimeError("fail")

        reactor = _reactor(_uniq("r"), failing)
        reactor.set_retry_strategy(EventRetryStrategy.RetryNever, 1)
        assert self._run_with_timeout(reactor), "execute 未在超时内返回（死循环）"
        assert len(calls) == 1

    def test_retry_forever_retries_until_success(self):
        """Scenario: 永久重试的策略在回调成功前持续重试."""
        calls = []

        def flaky(req):
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("fail")

        reactor = _reactor(_uniq("r"), flaky)
        reactor.set_retry_strategy(EventRetryStrategy.RetryForever, 0)
        assert self._run_with_timeout(reactor), "execute 未返回"
        assert len(calls) == 2

    def test_retry_times_calls_exactly_requested_count(self):
        """Scenario: 固定次数的策略按声明次数重试."""
        calls = []

        def failing(req):
            calls.append(1)
            raise RuntimeError("fail")

        reactor = _reactor(_uniq("r"), failing)
        reactor.set_retry_strategy(EventRetryStrategy.RetryTimes, 3)
        assert self._run_with_timeout(reactor), "execute 未返回"
        assert len(calls) == 3

    def test_retry_always_invokes_handler_on_success(self):
        """Scenario: 始终重试的策略在回调成功时只执行一次."""
        calls = []

        def succeeding(req):
            calls.append(1)

        reactor = _reactor(_uniq("r"), succeeding)
        reactor.set_retry_strategy(EventRetryStrategy.RetryAlways, 1)
        assert self._run_with_timeout(reactor), "execute 未返回"
        assert len(calls) == 1


class TestReactorPriority:
    """event-dispatch: 响应器优先级 MUST 由系统优先级与用户优先级共同决定."""

    def test_priority_is_integer(self):
        """Scenario: 读取综合优先级返回整数."""
        assert isinstance(_reactor(_uniq("p"), lambda _: None).get_priority(), int)

    def test_system_priority_affects_comparison(self):
        """Scenario: 系统优先级影响综合优先级."""
        low = _reactor(_uniq("p"), lambda _: None)
        high = _reactor(_uniq("p"), lambda _: None)
        low.sys_priority = EventPriorities.LOW
        high.sys_priority = EventPriorities.HIGH
        low.user_priority = high.user_priority = EventPriorities.NORMAL
        assert high.get_priority() > low.get_priority()

    def test_user_priority_participates(self):
        """Scenario: 用户优先级参与综合优先级."""
        first = _reactor(_uniq("p"), lambda _: None)
        second = _reactor(_uniq("p"), lambda _: None)
        first.sys_priority = second.sys_priority = EventPriorities.NORMAL
        first.user_priority = EventPriorities.LOW
        second.user_priority = EventPriorities.HIGH
        assert first.get_priority() != second.get_priority()

    def test_priority_usable_for_sorting(self):
        """Scenario: 综合优先级可用于排序."""
        reactors = [_reactor(_uniq("p"), lambda _: None) for _ in range(3)]
        sorted(reactors, key=lambda r: r.get_priority())


class TestEventDispatch:
    """event-dispatch: 事件分发 MUST 按主题投递到匹配的响应器."""

    def test_dispatch_reaches_subscribed_reactor(self):
        """Scenario: 投递到订阅了该主题的响应器."""
        calls = []
        topic = _uniq("topic")
        EventReactorManager().bind_topic_reactor(
            topic, _reactor(_uniq("r"), lambda _: calls.append(1))
        )
        EventReactorManager().dispatch(topic, "content")
        assert len(calls) == 1

    def test_dispatch_without_reactors_returns_silently(self):
        """Scenario: 无响应器订阅时静默返回."""
        EventReactorManager().dispatch(_uniq("no_such_topic"), "content")


class TestEventChannelIdentity:
    """event-dispatch: 事件 MUST 携带发布通道标识."""

    def test_dispatch_preserves_caller_channel(self):
        """Scenario: 指定通道的事件保留通道名."""
        fifo = EventFIFO()
        channel = _uniq("business")
        fifo.dispatch("topic", "content", channel)
        assert fifo.get_top().channel_name == channel

    def test_dispatch_defaults_to_default_channel(self):
        """Scenario: 未指定通道时归入默认通道."""
        fifo = EventFIFO()
        fifo.dispatch("topic", "content")
        assert fifo.get_top().channel_name == "default"


class TestChannelIsolation:
    """event-dispatch: 通道之间的事件队列 MUST 相互隔离."""

    def test_channels_hold_distinct_queues(self):
        """Scenario: 通道的队列实例互不相同."""
        first = EventChannel(_uniq("ch"))
        second = EventChannel(_uniq("ch"))
        assert first._event_fifo is not second._event_fifo

    def test_event_in_one_channel_is_invisible_to_another(self):
        """Scenario: 不同通道的队列互不可见."""
        first = EventChannel(_uniq("ch"))
        second = EventChannel(_uniq("ch"))
        first.push_event(EventNode(topic="t", content="c"))
        assert second.size() == 0
        assert first.size() == 1

    def test_event_of_one_channel_not_popped_by_another(self):
        """Scenario: 通道 A 的事件不被通道 B 弹出."""
        first = EventChannel(_uniq("ch"))
        second = EventChannel(_uniq("ch"))
        first.push_event(EventNode(topic="t", content="c"))
        assert second.pop_value() is None
        assert first.size() == 1


class TestEventContainmentQuery:
    """event-dispatch: 事件包含性查询 MUST 返回布尔结果."""

    def test_absent_event_returns_false(self):
        """Scenario: 查询不存在的事件."""
        fifo = EventFIFO()
        assert fifo.has_event(EventNode(topic="absent", content="x")) is False

    def test_present_event_returns_true(self):
        """Scenario: 查询已入队的事件."""
        fifo = EventFIFO()
        node = EventNode(topic=_uniq("t"), content="x")
        fifo.push_value(node)
        assert fifo.has_event(EventNode(topic=node.topic, content="x")) is True

    def test_query_on_empty_queue_returns_false(self):
        """Scenario: 对空队列查询."""
        assert EventFIFO().has_event(EventNode(topic="t", content="c")) is False

    def test_refresh_of_absent_event_does_not_raise(self):
        """包含性查询的调用方语义：事件不在队列时刷新应静默不做处理."""
        channel = EventChannel(_uniq("ch"))
        channel.refresh_event(EventNode(topic="absent", content="x"))


class TestResponseMechanism:
    """event-dispatch: 响应机制 MUST 按声明选择响应器集合."""

    def _channel_with_reactors(self, count=3):
        channel = EventChannel(_uniq("ch"))
        topic = _uniq("topic")
        reactors = [_reactor(_uniq("r"), lambda _: None) for _ in range(count)]
        for reactor in reactors:
            channel.register_reactor(topic, reactor)
        return topic, reactors

    def test_mechanism_one_selects_first_only(self):
        """Scenario: 机制一仅选出首个响应器."""
        topic, _ = self._channel_with_reactors(3)
        node = EventNode(topic=topic, content="c")
        node.set_response_mechanism(1)
        assert len(EventChannelManager().get_channel_reactors(node)) == 1

    def test_mechanism_two_sorted_by_priority_desc(self):
        """Scenario: 机制二选出全部并按优先级排序."""
        topic, reactors = self._channel_with_reactors(3)
        for index, reactor in enumerate(reactors):
            reactor.sys_priority = EventPriorities.LOW if index == 0 else EventPriorities.HIGH
            reactor.user_priority = EventPriorities.NORMAL
        node = EventNode(topic=topic, content="c")
        node.set_response_mechanism(2)
        selected = EventChannelManager().get_channel_reactors(node)
        assert len(selected) == 3
        priorities = [reactor.get_priority() for reactor in selected]
        assert priorities == sorted(priorities, reverse=True)

    def test_mechanism_three_selects_all(self):
        """Scenario: 机制三选出全部响应器."""
        topic, _ = self._channel_with_reactors(3)
        node = EventNode(topic=topic, content="c")
        node.set_response_mechanism(3)
        assert len(EventChannelManager().get_channel_reactors(node)) == 3

    def test_mechanism_four_selects_named_reactor(self):
        """Scenario: 机制四只选出指定响应器."""
        topic, reactors = self._channel_with_reactors(3)
        target = reactors[1]
        node = EventNode(topic=topic, content="c")
        node.set_response_mechanism(4, target.reactor_name)
        selected = EventChannelManager().get_channel_reactors(node)
        assert len(selected) == 1
        assert selected[0].reactor_name == target.reactor_name

    def test_mechanism_four_with_unknown_name_returns_empty(self):
        """Scenario: 机制四指定的名称不存在."""
        topic, _ = self._channel_with_reactors(2)
        node = EventNode(topic=topic, content="c")
        node.set_response_mechanism(4, _uniq("ghost"))
        assert EventChannelManager().get_channel_reactors(node) == []

    def test_mechanism_four_without_name_raises(self):
        """Scenario: 机制四未指定名称时拒绝构造."""
        node = EventNode(topic="t", content="c")
        with pytest.raises(ValueError):
            node.set_response_mechanism(4)


# =============================================================================
# C 组 · 行为修正（state-machine / worker-lifecycle）
# =============================================================================


class TestStateWrite:
    """state-machine: 状态写入 MUST 对任意键路径生效."""

    def test_top_level_key_overwrites(self):
        """Scenario: 顶层键的重复写入覆盖旧值."""
        scope = _uniq("scope")
        manager = StateMachineManager()
        manager.set_state(scope, "k", 1)
        manager.set_state(scope, "k", 42)
        assert manager.get_state(scope, "k") == 42

    def test_nested_key_overwrites(self):
        """Scenario: 嵌套键的重复写入覆盖旧值."""
        scope = _uniq("scope")
        manager = StateMachineManager()
        manager.set_state(scope, "a.b", 1)
        manager.set_state(scope, "a.b", 2)
        assert manager.get_state(scope, "a.b") == 2

    def test_first_write_creates_key(self):
        """Scenario: 首次写入自动创建."""
        scope = _uniq("scope")
        manager = StateMachineManager()
        manager.set_state(scope, "fresh", 7)
        assert manager.get_state(scope, "fresh") == 7

    def test_remove_then_read_returns_none(self):
        """Scenario: 写入后删除."""
        scope = _uniq("scope")
        manager = StateMachineManager()
        manager.set_state(scope, "gone", 1)
        manager.remove_state(scope, "gone")
        assert manager.get_state(scope, "gone") is None

    def test_top_level_and_nested_have_same_write_semantics(self):
        """Scenario: 顶层键与嵌套键的写入语义一致."""
        scope = _uniq("scope")
        manager = StateMachineManager()
        for key in ("toplevel", "branch.leaf"):
            manager.set_state(scope, key, 1)
            manager.set_state(scope, key, 2)
            assert manager.get_state(scope, key) == 2, f"{key} 的覆盖写入未生效"


class TestStateObservation:
    """state-machine: 观察者注册 MUST 对任意键路径生效."""

    def test_observe_existing_key_notifies(self):
        """Scenario: 对已存在的键注册观察者."""
        scope, key = _uniq("scope"), "a.b"
        seen = []
        manager = StateMachineManager()
        manager.set_state(scope, key, 0)
        manager.observe_state(scope, key, lambda payload: seen.append(payload["value"]))
        manager.set_state(scope, key, 5)
        assert seen == [5]

    def test_observe_absent_key_is_not_dropped(self):
        """Scenario: 对尚不存在的键注册观察者."""
        scope, key = _uniq("scope"), _uniq("ghost")
        seen = []
        manager = StateMachineManager()
        manager.observe_state(scope, key, lambda payload: seen.append(payload["value"]))
        manager.set_state(scope, key, 9)
        assert seen == [9], "对不存在的键注册的观察者被静默丢弃"

    def test_consecutive_writes_notify_each_time(self):
        """Scenario: 连续写入触发多次通知."""
        scope, key = _uniq("scope"), "a.b"
        seen = []
        manager = StateMachineManager()
        manager.set_state(scope, key, 0)
        manager.observe_state(scope, key, lambda payload: seen.append(payload["value"]))
        manager.set_state(scope, key, 1)
        manager.set_state(scope, key, 2)
        assert seen == [1, 2]

    def test_multiple_observers_all_notified(self):
        """Scenario: 多个观察者都被通知."""
        scope, key = _uniq("scope"), "a.b"
        first, second = [], []
        manager = StateMachineManager()
        manager.set_state(scope, key, 0)
        manager.observe_state(scope, key, lambda _: first.append(1))
        manager.observe_state(scope, key, lambda _: second.append(1))
        manager.set_state(scope, key, 1)
        assert len(first) == 1 and len(second) == 1

    def test_unobserve_stops_notifications(self):
        """Scenario: 注销后不再通知."""
        scope, key = _uniq("scope"), "a.b"
        seen = []

        def observer(payload):
            seen.append(payload["value"])

        manager = StateMachineManager()
        manager.set_state(scope, key, 0)
        manager.observe_state(scope, key, observer)
        manager.set_state(scope, key, 1)
        manager.unobserve_state(scope, key, observer)
        manager.set_state(scope, key, 2)
        assert seen == [1]

    def test_unobserve_absent_key_raises_keyerror(self):
        """Scenario: 注销不存在的键抛出 KeyError."""
        manager = StateMachineManager()
        with pytest.raises(KeyError):
            manager.unobserve_state(_uniq("scope"), _uniq("absent"), lambda _: None)

    def test_unobserve_one_keeps_other_observer(self):
        """Scenario: 注销其中一个观察者不影响其他观察者."""
        scope, key = _uniq("scope"), "a.b"
        kept, dropped = [], []

        def to_drop(payload):
            dropped.append(1)

        manager = StateMachineManager()
        manager.set_state(scope, key, 0)
        manager.observe_state(scope, key, lambda _: kept.append(1))
        manager.observe_state(scope, key, to_drop)
        manager.unobserve_state(scope, key, to_drop)
        manager.set_state(scope, key, 1)
        assert len(kept) == 1 and dropped == []


class _ConcreteAsyncWorker(AsyncWorker):
    """用于测试的最小异步 Worker 实现."""

    def __init__(self, name=None):
        super().__init__(name)

    async def async_execute(self, *args, **kwargs):
        return "async-result"


class TestAsyncWorkerProperties:
    """worker-lifecycle: 异步 Worker MUST 以属性字典承载配置."""

    def test_name_is_readable(self):
        """Scenario: 读取异步 Worker 的名称."""
        worker = _ConcreteAsyncWorker(_uniq("AW"))
        assert "AW" in worker.name

    def test_name_readable_without_explicit_name(self):
        """Scenario: 未传名称时读取异步 Worker 的名称."""
        assert _ConcreteAsyncWorker().name

    def test_loop_flag_defaults_to_false(self):
        """Scenario: 读取异步 Worker 的循环标志."""
        assert _ConcreteAsyncWorker(_uniq("AW")).is_loop() is False


class TestAsyncWorkerLifecycle:
    """worker-lifecycle: 异步 Worker 的生命周期日志 MUST 可安全执行."""

    def test_async_init_succeeds(self):
        """Scenario: 异步初始化成功."""
        asyncio.run(_ConcreteAsyncWorker(_uniq("AW")).async_init())

    def test_async_destroy_succeeds(self):
        """Scenario: 异步销毁成功."""
        asyncio.run(_ConcreteAsyncWorker(_uniq("AW")).async_destroy())

    def test_sync_execute_logging_path_works(self):
        """Scenario: 同步执行入口的日志路径可用."""
        assert _ConcreteAsyncWorker(_uniq("AW")).execute() == "async-result"


# =============================================================================
# 集成（task 1.2）：此前完全未被覆盖的主执行路径
# =============================================================================


class TestMasterIntegration:
    """主路径集成：构造 → 调度循环 → 事件端到端分发."""

    @pytest.fixture
    def isolated_master(self, tmp_path, monkeypatch):
        """把状态机持久化与日志路径重定向到临时目录，避免污染仓库根."""
        from zoo_framework.params import LogParams, StateMachineParams

        monkeypatch.setattr(StateMachineParams, "PICKLE_PATH", str(tmp_path / "states.pic"))
        monkeypatch.setattr(LogParams, "LOG_BASE_PATH", str(tmp_path / "logs"))
        master = Master()
        yield master
        master.shutdown()

    def test_scheduling_round_runs(self, isolated_master):
        """构造后可跑通多轮调度而不抛异常."""
        for _ in range(3):
            isolated_master.waiter.execute_service()

    def test_event_channel_end_to_end(self, isolated_master):
        """事件从入队到被响应器处理的端到端路径，且主题与内容不互换."""
        received = []
        topic = _uniq("topic")
        channel_name = _uniq("e2e")
        # 必须经 refresh_channel 建立通道并绑定响应器——直接构造 EventChannel
        # 不会注册进 EventChannelRegister，EventWorker 遍历不到它
        EventChannelManager().refresh_channel(
            channel_name, topic, _reactor(_uniq("r"), received.append)
        )
        channel = EventChannelManager().get_channel(channel_name)
        # dispatch 会把通道名写到事件上（覆盖通道标识的修复）
        channel.dispatch(topic, "payload")

        # execute_service 把 worker 派发到后台线程后立即返回，因此必须等待后台
        # 线程完成，不能在调用后立刻断言。
        isolated_master.waiter.execute_service()
        deadline = time.time() + 10
        while time.time() < deadline and not received:
            time.sleep(0.05)

        assert len(received) == 1, "事件未被端到端投递到响应器"
        # 响应器收到的是 EventReactorReq：实参顺序写反会让二者互换
        assert received[0].topic == topic
        assert received[0].content == "payload"
