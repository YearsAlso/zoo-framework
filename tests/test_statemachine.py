"""State Machine 测试

测试状态机相关功能
"""

import pytest
from unittest.mock import MagicMock

from zoo_framework.statemachine.state_node import StateNode
from zoo_framework.statemachine.state_effect import StateEffect


class TestStateNode:
    """StateNode 测试类"""

    def test_state_node_creation(self):
        """测试创建 StateNode"""
        node = StateNode(
            key="test.key",
            value="test_value",
        )
        
        assert node._key == "test.key"
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


class TestStateEffect:
    """StateEffect 测试类"""

    def test_state_effect_execute(self):
        """测试执行 Effect"""
        executed = []
        
        def callback(old_val, new_val):
            executed.append((old_val, new_val))
        
        effect = StateEffect(callback=callback)
        
        effect.execute("old", "new")
        
        assert len(executed) == 1
        assert executed[0] == ("old", "new")
