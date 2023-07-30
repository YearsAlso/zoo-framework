from zoo_framework.reactor import EventReactor
from zoo_framework.core.aop import cage
from .event_channel_register import EventChannelRegister
from .event_channel import EventChannel


@cage
class EventChannelManager:
    """
    事件通道管理器
    """

    _event_channel_register: EventChannelRegister = EventChannelRegister()

    @classmethod
    def refresh_channel(cls, channel_name, topic, reactor: EventReactor):
        """
        刷新事件通道
        """
        channel: EventChannel = cls._event_channel_register.register(channel_name)
        channel.register_reactor(topic, reactor)

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
    def get_channel_count(cls):
        """
        获取事件通道数量
        """
        return cls._event_channel_register.get_channel_count()

    @classmethod
    def perform(cls, channel_name, topic, content):
        """
        分发事件
        """
        channel: EventChannel = cls._event_channel_register.get_channel(channel_name)

        # 获得所有的事件反应器
        # 并且将事件放入事件队列
        if channel:
            reactors = channel.get_reactor(topic)
            for reactor in reactors:
                reactor.execute(topic, content)
        else:
            raise Exception("channel not found")

    @classmethod
    def get_perform_reactors(cls, channel_name, topic):
        """
        获取事件通道的事件反应器
        """
        channel: EventChannel = cls._event_channel_register.get_channel(channel_name)

        # 获得所有的事件反应器
        # 并且将事件放入事件队列
        if channel:
            reactors = channel.get_reactor(topic)
            return reactors
        else:
            raise Exception("channel not found")
