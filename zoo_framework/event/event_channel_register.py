"""event_channel_register - zoo_framework/event/event_channel_register.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta

from zoo_framework.core.aop import cage
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

from .event_channel import EventChannel


@cage
class EventChannelRegister:
    """事件通道注册器."""

    _single = None
    _instance = None

    # 事件通道字典
    _channel_map: ThreadSafeDict = ThreadSafeDict()

    @classmethod
    def register(cls, channel_name):
        channel = cls.get_channel(channel_name)
        if channel is None:
            channel = EventChannel(channel_name)
            cls._channel_map[channel_name] = channel
        return channel

    @classmethod
    def unregister(cls, channel_name):
        cls._channel_map.pop(channel_name)

    @classmethod
    def get_channel(cls, channel_name) -> EventChannel:
        if channel_name not in cls._channel_map:
            # 创建事件通道
            from zoo_framework.event.event_channel import EventChannel

            cls._channel_map[channel_name] = EventChannel(channel_name)
            return cls._channel_map.get(channel_name)
        return cls._channel_map.get(channel_name)

    @classmethod
    def get_all_channel(cls):
        return cls._channel_map.get_values()

    @classmethod
    def get_channel_name_list(cls):
        return cls._channel_map.get_keys()

    @classmethod
    def get_channel_count(cls):
        return len(cls._channel_map)
"""
