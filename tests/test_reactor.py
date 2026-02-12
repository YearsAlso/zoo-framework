"""Reactor 测试模块

测试事件响应器功能
"""

import pytest

from zoo_framework.reactor.event_reactor_req import (
    EventReactorReq,
    ChannelType,
    ChannelManager,
)


class TestChannelType:
    """ChannelType 测试类"""

    def test_channel_type_values(self):
        """测试 ChannelType 枚举值"""
        assert ChannelType.DEFAULT.value == "default"
        assert ChannelType.SYSTEM.value == "system"
        assert ChannelType.BUSINESS.value == "business"
        assert ChannelType.LOG.value == "log"
        assert ChannelType.ERROR.value == "error"


class TestEventReactorReq:
    """EventReactorReq 测试类"""

    def test_event_reactor_req_init(self):
        """测试 EventReactorReq 初始化"""
        req = EventReactorReq(
            topic="test.topic",
            content="test_content",
            reactor_name="test_reactor"
        )

        assert req.topic == "test.topic"
        assert req.content == "test_content"
        assert req.reactor_name == "test_reactor"
        assert req.channel == ChannelType.DEFAULT.value

    def test_event_reactor_req_with_channel(self):
        """测试带通道的 EventReactorReq"""
        req = EventReactorReq(
            topic="test.topic",
            content="test_content",
            reactor_name="test_reactor",
            channel=ChannelType.BUSINESS.value,
            priority=10
        )

        assert req.channel == ChannelType.BUSINESS.value
        assert req.priority == 10

    def test_event_reactor_req_match_channel(self):
        """测试通道匹配"""
        req = EventReactorReq(
            topic="test.topic",
            content="test_content",
            reactor_name="test_reactor",
            channel=ChannelType.BUSINESS.value
        )

        assert req.match_channel([ChannelType.BUSINESS.value]) is True
        assert req.match_channel([ChannelType.SYSTEM.value]) is False
        assert req.match_channel([ChannelType.BUSINESS.value, ChannelType.SYSTEM.value]) is True

    def test_event_reactor_req_repr(self):
        """测试 EventReactorReq 字符串表示"""
        req = EventReactorReq(
            topic="test.topic",
            content="test_content",
            reactor_name="test_reactor"
        )

        repr_str = repr(req)
        assert "EventReactorReq" in repr_str
        assert "test.topic" in repr_str


class TestChannelManager:
    """ChannelManager 测试类"""

    def test_channel_manager_init(self):
        """测试 ChannelManager 初始化"""
        manager = ChannelManager()
        assert manager is not None

    def test_channel_manager_register_channel(self):
        """测试注册通道"""
        manager = ChannelManager()

        manager.register_channel("custom_channel", ["topic1", "topic2"])

        assert manager.is_channel_valid("custom_channel") is True
        assert manager.is_channel_valid("invalid_channel") is False

    def test_channel_manager_register_reactor_channels(self):
        """测试注册响应器通道"""
        manager = ChannelManager()

        manager.register_reactor_channels("test_reactor", [ChannelType.BUSINESS.value, ChannelType.SYSTEM.value])

        # 创建事件
        event = EventReactorReq(
            topic="test.topic",
            content="test",
            reactor_name="test_reactor",
            channel=ChannelType.BUSINESS.value
        )

        assert manager.can_handle_event("test_reactor", event) is True

        # 未授权的通道
        event2 = EventReactorReq(
            topic="test.topic",
            content="test",
            reactor_name="test_reactor",
            channel=ChannelType.ERROR.value
        )

        assert manager.can_handle_event("test_reactor", event2) is False

    def test_channel_manager_get_channel_topics(self):
        """测试获取通道主题"""
        manager = ChannelManager()

        manager.register_channel("test_channel", ["topic1", "topic2", "topic3"])

        topics = manager.get_channel_topics("test_channel")
        assert "topic1" in topics
        assert "topic2" in topics
        assert "topic3" in topics
