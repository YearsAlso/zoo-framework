"""event_channel - zoo_framework/event/event_channel.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.fifo import EventFIFO
from zoo_framework.fifo.node import EventNode
from zoo_framework.reactor import EventReactor, EventReactorManager
from zoo_framework.utils import LogUtils


class EventChannel:
    """事件通道."""

    # 事件队列
    _event_fifo: EventFIFO = EventFIFO()

    # 事件反应器管理器
    _reactor_manager = EventReactorManager()

    def __init__(self, channel_name):
        # 是否公开, 通道不公开时, 只能通过事件反应器来触发事件,如果公开, 则可以通过事件通道来触发事件
        self.public = False
        # 通道名称
        self.channel_name = channel_name

    def get_reactors(self, topic: str) -> list[EventReactor]:
        """获取事件反应器."""
        return self._reactor_manager.get_reactor(topic)

    def get_channel_name(self):
        """获取通道名称."""
        return self.channel_name

    def set_public(self, public):
        """设置是否公开."""
        self.public = public

    def is_public(self):
        """是否公开."""
        return self.public

    def size(self):
        """获取事件队列大小."""
        return self._event_fifo.size()

    def pop_value(self) -> EventNode:
        """从事件队列中弹出事件."""
        return self._event_fifo.pop_value()

    def get_top(self) -> EventNode:
        """获取事件队列的第一个事件."""
        return self._event_fifo.get_top()

    def push_event(self, event: EventNode):
        """将事件推入事件队列."""
        try:
            self._event_fifo.push_value(event)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    def dispatch(self, topic, content):
        """将事件推入事件队列."""
        self._event_fifo.dispatch(topic, content, self.channel_name)

    def register_reactor(self, topic, reactor):
        """注册事件反应器."""
        self._reactor_manager.bind_topic_reactor(topic, reactor)

    def refresh_event(self, event):
        """刷新事件."""
        # 判断管道中是否存在该事件
        if self._event_fifo.has_event(event):  # 如果存在
            # 替换事件
            self._event_fifo.replace(event)
