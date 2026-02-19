"""event_channel_manager - zoo_framework/event/event_channel_manager.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta
"""
from zoo_framework.core.aop import cage
from zoo_framework.reactor import EventReactor

from ..fifo.node import EventNode
from .event_channel import EventChannel
from .event_channel_register import EventChannelRegister


@cage
class EventChannelManager:
    """事件通道管理器."""

    _event_channel_register: EventChannelRegister = EventChannelRegister()

    @classmethod
    def refresh_channel(cls, channel_name, topic, reactor: EventReactor):
        """刷新事件频道."""
        channel: EventChannel = cls._event_channel_register.register(channel_name)
        channel.register_reactor(topic, reactor)

    @classmethod
    def get_channel(cls, channel_name) -> EventChannel:
        """获取事件频道."""
        return cls._event_channel_register.get_channel(channel_name)

    @classmethod
    def get_channel_register(cls):
        """获取频道通道注册器."""
        return cls._event_channel_register

    @classmethod
    def get_all_channel_name(cls):
        """获取事件频道名称列表."""
        return cls._event_channel_register.get_channel_name_list()

    @classmethod
    def get_all_channel_count(cls):
        """获取事件通道数量."""
        return cls._event_channel_register.get_channel_count()

    @classmethod
    def perform_event(cls, event: EventNode):
        """分发事件."""
        channel: EventChannel = cls._event_channel_register.get_channel(event.channel_name)

        # 获得所有的事件反应器
        # 并且将事件放入事件队列
        if channel is None:
            raise Exception("channel not found")
        # 获得事件响应策略
        if event.response_mechanism == 1:
            # 获得第一个事件反应器
            reactors: list[EventReactor] = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                reactors[0].execute(event.topic, event.content)
        elif event.response_mechanism == 2:
            # 根据事件优先级获得事件反应器
            reactors: list[EventReactor] = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                for reactor in reactors:
                    reactor.execute(event.topic, event.content)
        elif event.response_mechanism == 3:
            # 获得所有的事件反应器
            reactors: list[EventReactor] = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                for reactor in reactors:
                    reactor.execute(event.topic, event.content)
        elif event.response_mechanism == 4:
            # 获得所有的事件反应器
            reactors: list[EventReactor] = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                # 根据名称获得事件反应器
                for reactor in reactors:
                    if reactor.reactor_name == event.reactor_name:
                        reactor.execute(event.topic, event.content)

    @classmethod
    def get_channel_reactors(cls, event: EventNode) -> list[EventReactor] or None:
        """获取事件频道的事件反应器."""
        # 事件获得频道
        channel: EventChannel = cls._event_channel_register.get_channel(event.channel_name)

        # 获得所有的事件反应器
        # 并且将事件放入事件队列
        if channel is None:
            raise Exception("channel not found")
            return None

        # 获得事件响应策略
        if event.response_mechanism == 1:
            # 获得第一个事件反应器
            reactors: list[EventReactor] = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                return [reactors[0]]
        elif event.response_mechanism == 2:
            # 根据事件优先级获得事件反应器
            reactors: list[EventReactor] = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                return reactors.sort(key=lambda x: x.priority)
        elif event.response_mechanism == 3:
            # 获得所有的事件反应器
            reactors: list[EventReactor] = channel.get_reactors(event.topic)
            return reactors
        elif event.response_mechanism == 4:
            # 获得所有的事件反应器
            reactors: list[EventReactor] = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                # 根据名称获得事件反应器
                for reactor in reactors:
                    if reactor.reactor_name == event.reactor_name:
                        return [reactor]
        return []
