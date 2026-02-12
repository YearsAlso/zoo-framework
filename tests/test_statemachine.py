"""State Machine 测试

测试状态机相关功能
"""

import pytest
from unittest.mock import MagicMock

from zoo_framework.statemachine import StateNode, StateEffect
from zoo_framework.statemachine.state_node import StateNodeType


class TestStateNode:
    """StateNode 测试类"""

    def test_state_node_creation(self):
        """测试创建 StateNode"""
        node = StateNode(
            key="test.key",
            value="test_value",
            node_type=StateNodeType.NORMAL
        )
        
        assert node.key == "test.key"
        assert node.value == "test_value"
        assert node.node_type == StateNodeType.NORMAL

    def test_state_node_default_type(self):
        """测试默认节点类型"""
        node = StateNode(key="test.key", value="test_value")
        assert node.node_type == StateNodeType.NORMAL

    def test_state_node_set_value(self):
        """测试设置值"""
        node = StateNode(key="test.key", value="old_value")
        node.set_value("new_value")
        
        assert node.value == "new_value"

    def test_state_node_get_value(self):
        """测试获取值"""
        node = StateNode(key="test.key", value="test_value")
        assert node.get_value() == "test_value"

    def test_state_node_add_child(self):
        """测试添加子节点"""
        parent = StateNode(key="parent", value="parent_value")
        child = StateNode(key="parent.child", value="child_value")
        
        parent.add_child(child)
        
        assert child in parent.children

    def test_state_node_remove_child(self):
        """测试移除子节点"""
        parent = StateNode(key="parent", value="parent_value")
        child = StateNode(key="parent.child", value="child_value")
        
        parent.add_child(child)
        parent.remove_child(child)
        
        assert child not in parent.children

    def test_state_node_has_children(self):
        """测试是否有子节点"""
        parent = StateNode(key="parent", value="parent_value")
        
        assert parent.has_children() is False
        
        child = StateNode(key="parent.child", value="child_value")
        parent.add_child(child)
        
        assert parent.has_children() is True


class TestStateEffect:
    """StateEffect 测试类"""

    def test_state_effect_creation(self):
        """测试创建 StateEffect"""
        def callback(old_val, new_val):
            pass
        
        effect = StateEffect(
            target_key="test.key",
            callback=callback
        )
        
        assert effect.target_key == "test.key"
        assert effect.callback == callback

    def test_state_effect_execute(self):
        """测试执行 Effect"""
        executed = []
        
        def callback(old_val, new_val):
            executed.append((old_val, new_val))
        
        effect = StateEffect(
            target_key="test.key",
            callback=callback
        )
        
        effect.execute("old", "new")
        
        assert len(executed) == 1
        assert executed[0] == ("old", "new")

    def test_state_effect_matches(self):
        """测试 Effect 匹配"""
        effect = StateEffect(target_key="test.key", callback=lambda x, y: None)
        
        assert effect.matches("test.key") is True
        assert effect.matches("other.key") is False
        assert effect.matches("test.") is True  # 前缀匹配

    def test_state_effect_with_condition(self):
        """测试带条件的 Effect"""
        def callback(old_val, new_val):
            pass
        
        def condition(old_val, new_val):
            return new_val > old_val
        
        effect = StateEffect(
            target_key="test.key",
            callback=callback,
            condition=condition
        )
        
        # 条件满足时执行
        assert effect.should_execute(1, 2) is True
        # 条件不满足时不执行
        assert effect.should_execute(2, 1) is False


class TestStateNodeType:
    """StateNodeType 测试类"""

    def test_state_node_type_values(self):
        """测试 StateNodeType 枚举值"""
        from zoo_framework.statemachine.state_node_type import StateNodeType
        
        assert StateNodeType.NORMAL.value == "normal"
        assert StateNodeType.TEMPORARY.value == "temporary"
        assert StateNodeType.PERSISTENT.value == "persistent"
