"""State Machine 测试

测试状态机相关功能
"""

import pytest
from unittest.mock import MagicMock

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
