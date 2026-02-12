"""FIFO 和 Event Node 测试

测试 BaseFIFO、EventFIFO 和 EventNode
"""

import pytest
import time
from zoo_framework.fifo import BaseFIFO, EventFIFO
from zoo_framework.fifo.node import EventNode
from zoo_framework.fifo.node.event_fifo_node import (
    PriorityLevel,
    EventPriorityCalculator,
)


class TestBaseFIFO:
    """BaseFIFO 测试类"""

    def setup_method(self):
        """每个测试前清理"""
        BaseFIFO._fifo = []

    def test_push_and_pop(self):
        """测试入队和出队"""
        fifo = BaseFIFO()
        BaseFIFO.push_value("item1")
        BaseFIFO.push_value("item2")
        
        assert BaseFIFO.size() == 2
        
        item = BaseFIFO.pop_value()
        assert item == "item1"
        assert BaseFIFO.size() == 1

    def test_clear(self):
        """测试清空队列"""
        fifo = BaseFIFO()
        BaseFIFO.push_value("item1")
        BaseFIFO.push_value("item2")
        
        assert BaseFIFO.size() == 2
        BaseFIFO.clear()
        assert BaseFIFO.size() == 0

    def test_is_empty(self):
        """测试判断是否为空"""
        fifo = BaseFIFO()
        assert BaseFIFO.is_empty() is True
        
        BaseFIFO.push_value("item")
        assert BaseFIFO.is_empty() is False

    def test_peek(self):
        """测试查看队首元素"""
        fifo = BaseFIFO()
        BaseFIFO.push_value("item1")
        BaseFIFO.push_value("item2")
        
        item = BaseFIFO.peek()
        assert item == "item1"
        assert BaseFIFO.size() == 2  # peek 不改变队列大小


class TestEventNode:
    """EventNode 测试类"""

    def test_event_node_creation(self):
        """测试创建 EventNode"""
        node = EventNode(
            topic="test.topic",
            content="test content",
            channel_name="test_channel"
        )
        
        assert node.topic == "test.topic"
        assert node.content == "test content"
        assert node.channel_name == "test_channel"
        assert node.priority == 0

    def test_event_node_with_priority_level(self):
        """测试使用 PriorityLevel 创建 EventNode"""
        node = EventNode(
            topic="test.topic",
            content="test content",
            priority_level=PriorityLevel.HIGH
        )
        
        assert node.priority == PriorityLevel.HIGH.value

    def test_event_node_equality(self):
        """测试 EventNode 相等比较"""
        node1 = EventNode(topic="test", content="content")
        node2 = EventNode(topic="test", content="content")
        node3 = EventNode(topic="other", content="content")
        
        assert node1 == node2
        assert node1 != node3

    def test_event_node_hash(self):
        """测试 EventNode 哈希值"""
        node1 = EventNode(topic="test", content="content")
        node2 = EventNode(topic="test", content="content")
        
        assert hash(node1) == hash(node2)

    def test_event_node_comparison(self):
        """测试 EventNode 优先级比较"""
        node1 = EventNode(topic="test1", content="content", priority=100)
        time.sleep(0.01)  # 确保创建时间不同
        node2 = EventNode(topic="test2", content="content", priority=200)
        
        assert node1 < node2  # node2 优先级更高
        assert node2 > node1

    def test_get_effective_priority(self):
        """测试获取有效优先级"""
        node = EventNode(topic="test", content="content", priority=100)
        effective_priority = node.get_effective_priority()
        
        assert effective_priority >= 100

    def test_set_timeout(self):
        """测试设置超时"""
        def timeout_callback(node):
            pass
        
        node = EventNode(topic="test", content="content")
        node.set_timeout(1, timeout_callback)
        
        assert node.timeout == 1
        assert node.timeout_response == timeout_callback

    def test_is_expire(self):
        """测试判断是否过期"""
        node = EventNode(topic="test", content="content")
        node.set_timeout(0.01)
        
        assert node.is_expire() is False
        time.sleep(0.02)
        assert node.is_expire() is True

    def test_increment_retry(self):
        """测试增加重试次数"""
        node = EventNode(topic="test", content="content")
        assert node.get_retry_times() == 0
        
        node.increment_retry()
        assert node.get_retry_times() == 1
        
        node.increment_retry()
        assert node.get_retry_times() == 2


class TestEventPriorityCalculator:
    """EventPriorityCalculator 测试类"""

    def test_calculate_priority(self):
        """测试优先级计算"""
        create_time = time.time()
        priority = EventPriorityCalculator.calculate(
            priority=100,
            create_time=create_time,
            wait_time_weight=0.3
        )
        
        assert priority >= 100

    def test_calculate_with_wait_time(self):
        """测试带等待时间的优先级计算"""
        create_time = time.time() - 10  # 10秒前创建
        priority = EventPriorityCalculator.calculate(
            priority=100,
            create_time=create_time,
            wait_time_weight=0.5
        )
        
        # 等待时间越长，优先级越高
        assert priority > 100

    def test_get_urgency_level(self):
        """测试获取紧急程度"""
        assert EventPriorityCalculator.get_urgency_level(1000) == "🔴 紧急"
        assert EventPriorityCalculator.get_urgency_level(500) == "🟠 高"
        assert EventPriorityCalculator.get_urgency_level(100) == "🟡 中"
        assert EventPriorityCalculator.get_urgency_level(10) == "🟢 低"
        assert EventPriorityCalculator.get_urgency_level(1) == "⚪ 后台"


class TestEventFIFO:
    """EventFIFO 测试类"""

    def setup_method(self):
        """每个测试前清理"""
        BaseFIFO._fifo = []

    def test_push_event_node(self):
        """测试推送 EventNode"""
        fifo = EventFIFO()
        node = EventNode(topic="test", content="content")
        
        fifo.push_value(node)
        assert fifo.size() == 1

    def test_push_dict(self):
        """测试推送字典"""
        fifo = EventFIFO()
        
        fifo.push_value({
            "topic": "test",
            "content": "content"
        })
        assert fifo.size() == 1

    def test_dispatch(self):
        """测试 dispatch 方法"""
        fifo = EventFIFO()
        
        fifo.dispatch("test.topic", "test content")
        assert fifo.size() == 1
        
        node = fifo.get_top()
        assert node.topic == "test.topic"
        assert node.content == "test content"

    def test_get_top_empty(self):
        """测试获取队首 - 空队列"""
        fifo = EventFIFO()
        top = fifo.get_top()
        assert top is None

    def test_has_event(self):
        """测试判断事件是否存在"""
        fifo = EventFIFO()
        node = EventNode(topic="test", content="content")
        
        fifo.push_value(node)
        assert fifo.has_event(node) is True

    def test_replace(self):
        """测试替换事件"""
        fifo = EventFIFO()
        node1 = EventNode(topic="test", content="content1")
        node2 = EventNode(topic="test", content="content2")
        
        fifo.push_value(node1)
        fifo.replace(node2)
        
        top = fifo.get_top()
        assert top.content == "content2"
