"""State Machine 测试

测试状态机相关功能
"""

import time

import zoo_framework.statemachine.state_node as _state_node_module
from zoo_framework.statemachine.state_effect import StateEffect
from zoo_framework.statemachine.state_effect_scheduler import StateEffectScheduler
from zoo_framework.statemachine.state_node import StateNode


class TestStateNode:
    """StateNode 测试类"""

    def test_state_node_creation(self):
        """测试创建 StateNode"""
        node = StateNode(
            key="test.key",
            value="test_value",
        )

        assert node.key == "test.key"
        assert node._value == "test_value"

    def test_state_node_get_key(self):
        """测试获取 key"""
        node = StateNode(key="test.key", value="test_value")
        assert node.get_key() == "test.key"

    def test_state_node_get_value(self):
        """测试获取值"""
        node = StateNode(key="test.key", value="test_value")
        assert node.get_value() == "test_value"

    def test_state_node_set_value(self):
        """测试设置值"""
        node = StateNode(key="test.key", value="old_value")
        node.set_value("new_value")

        assert node.get_value() == "new_value"

    def test_state_node_add_child(self):
        """测试添加子节点"""
        parent = StateNode(key="parent", value="parent_value")
        child = StateNode(key="parent.child", value="child_value")

        parent.add_child(child)

        assert child in parent._children

    def test_state_node_is_top(self):
        """测试根节点设置"""
        node = StateNode(key="test.key", value="test_value")

        assert node.is_top() is False

        node.to_be_top()
        assert node.is_top() is True


def _slow_effect(payload):
    time.sleep(0.3)


def _raising_effect(payload):
    raise RuntimeError("effect boom")


class TestStateNodeEffects:
    """align-execution-primitives: effect 以线程原语并发执行且有界等待."""

    def test_effects_run_once_each_with_payload(self):
        """Scenario: effect 正常执行各一次，载荷含值与版本."""
        calls: list[dict] = []
        node = StateNode(key="fx.key", value="old")
        node.add_effect(lambda payload: calls.append(payload))
        node.add_effect(lambda payload: calls.append(dict(payload)))

        node.set_value("new")

        assert len(calls) == 2
        assert all(c["value"] == "new" for c in calls)
        assert all("version" in c for c in calls)

    def test_slow_effect_does_not_hang_write(self, monkeypatch):
        """Scenario: 慢 effect 不挂死写路径——写入在超时后正常返回."""
        monkeypatch.setattr(_state_node_module, "_EFFECT_JOIN_TIMEOUT_SECONDS", 0.05)
        node = StateNode(key="fx.slow", value="old")
        node.add_effect(_slow_effect)

        start = time.monotonic()
        node.set_value("new")
        elapsed = time.monotonic() - start

        assert elapsed < 0.3, "写路径被慢 effect 挂死，未在有界超时处返回"
        assert node.get_value() == "new"

    def test_effect_exception_not_raised_but_logged(self, monkeypatch):
        """Scenario: effect 异常不传播给写入方，但被记入日志."""
        warnings: list[str] = []

        class _CapturingLog:
            @staticmethod
            def warning(message, *_args, **_kwargs):
                warnings.append(str(message))

        monkeypatch.setattr(_state_node_module, "LogUtils", _CapturingLog)
        node = StateNode(key="fx.raise", value="old")
        node.add_effect(_raising_effect)

        node.set_value("new")  # 不抛出

        assert node.get_value() == "new"
        assert any("effect" in w for w in warnings), "effect 异常被吞掉，未被可观测上报"


class TestStateEffectIndex:
    """state-machine: StateEffectScheduler MUST 能把 effect 登记进索引（issue #208）.

    缺陷：`StateEffectScheduler.add_state_effect` / `remove_state_effect` 调用
    `StateNodeIndex.add_state_effect` / `remove_state_effect`，而索引上并无这两个
    方法——一旦该路径被构造即 `AttributeError`（此前是死代码，故未被发现）。
    """

    @staticmethod
    def _effect(state="scope.state"):
        """构造一个不产生副作用的 StateEffect."""
        return StateEffect(state, lambda **_kwargs: None)

    def test_add_state_effect_reaches_the_index(self):
        """Scenario: 新增 effect 后索引按状态记账."""
        scheduler = StateEffectScheduler(None)
        effect = self._effect()

        scheduler.add_state_effect(effect)

        index = scheduler.get_state_effect_index()
        assert effect in index.state_effect_map[effect.state], "索引未按状态登记该 effect"
        assert effect in index.state_effect_set, "索引的全集未登记该 effect"

    def test_remove_state_effect_clears_the_index(self):
        """Scenario: 移除 effect 后索引不再包含它."""
        scheduler = StateEffectScheduler(None)
        effect = self._effect()
        scheduler.add_state_effect(effect)

        scheduler.remove_state_effect(effect)

        index = scheduler.get_state_effect_index()
        assert effect not in index.state_effect_set
        assert effect not in index.state_effect_map.get(effect.state, set())

    def test_scheduler_query_and_execute_semantics_unchanged(self):
        """补齐索引接口 MUST NOT 改变调度器既有的查询/执行语义."""
        scheduler = StateEffectScheduler(None)
        calls: list[dict] = []
        effect = StateEffect("scope.state", lambda **kwargs: calls.append(kwargs))
        scheduler.add_state_effect(effect)

        assert scheduler.get_state_effect("scope.state") == {effect}
        scheduler.execute_state_effect("scope.state", value=1)

        assert calls == [{"value": 1}], "effect 未被按预期执行"
