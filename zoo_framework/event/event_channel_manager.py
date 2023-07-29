from zoo_framework.core.aop import cage
from .event_channel_register import EventChannelRegister
from .event_channel import EventChannel


@cage
class EventChannelManager:
    """
    事件通道管理器
    """

    _event_channel_register = EventChannelRegister()

    @classmethod
    def register_channel(cls, channel_name, channel: EventChannel = None):
        """
        注册事件通道
        """
        if channel is None:
            channel = EventChannel(channel_name)
        cls._event_channel_register.register_channel(channel_name, channel)

    @classmethod
    def get_channel(cls, channel_name) -> EventChannel:
        """
        获取事件通道
        """
        return cls._event_channel_register.get_channel(channel_name)

    @classmethod
    def get_channel_register(cls):
        """
        获取事件通道注册器
        """
        return cls._event_channel_register

    @classmethod
    def get_channel_name_list(cls):
        """
        获取事件通道名称列表
        """
        return cls._event_channel_register.get_channel_name_list()

    @classmethod
    def get_channel(cls, channel_name):
        """
        获取事件通道
        """
        return cls._event_channel_register.get_channel(channel_name)
