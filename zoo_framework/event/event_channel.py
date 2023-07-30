from zoo_framework.fifo.node import EventFIFONode
from zoo_framework.reactor import EventReactorManager, EventReactor
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
        # 是否公开, 通道不公开时, 只能通过事件反应器来触发事件,如果公开, 则可以通过事件通道来触发事件
        self.public = False
        # 通道名称
        self.channel_name = channel_name

    def get_reactor(self, reactor_name) -> EventReactor:
        """
        获取事件反应器
        """
        return self._reactor_manager.get_reactor(reactor_name)

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

    def size(self):
        """
        获取事件队列大小
        """
        return self._event_fifo.size()

    def pop_value(self) -> EventFIFONode:
        """
        从事件队列中弹出事件
        """
        return self._event_fifo.pop_value()

    def get_top(self) -> EventFIFONode:
        """
        获取事件队列的第一个事件
        """
        return self._event_fifo.get_top()

    def push_topic(self, value):
        """
        将事件推入事件队列
        """
        try:
            _event_fifo = self._event_fifo.push_value(value)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    def dispatch(self, topic, content):
        """
        将事件推入事件队列
        """
        self._event_fifo.dispatch(topic, content, self.channel_name)

    def register_reactor(self, reactor):
        """
        注册事件反应器
        """
        self._reactor_manager.register(reactor)
