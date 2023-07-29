from zoo_framework import EventReactorManager
from zoo_framework.fifo import EventFIFO
from zoo_framework.utils import LogUtils


class EventChannel:
    """
    事件通道
    """

    # 事件队列
    _event_fifo: EventFIFO = EventFIFO()

    # 事件反应器管理器
    _reactor_manager = EventReactorManager()

    def __init__(self, channel_name):
        # 是否公开, 通道不公开时, 只能通过事件反应器来触发
        self.public = False
        # 通道名称
        self.channel_name = channel_name

    def get_channel_name(self):
        """
        获取通道名称
        """
        return self.channel_name

    def set_public(self, public):
        """
        设置是否公开
        """
        self.public = public

    def is_public(self):
        """
        是否公开
        """
        return self.public

    @classmethod
    def push_topic(cls, value):
        """
        将事件推入事件队列
        """
        try:
            _event_fifo = cls._event_fifo.push_value(value)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    @classmethod
    def dispatch(cls, topic, content, channel_name="default"):
        """
        将事件推入事件队列
        """
        cls._event_fifo.dispatch(topic, content, channel_name)
