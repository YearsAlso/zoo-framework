from .node import EventNode
from .base_fifo import BaseFIFO
from zoo_framework.utils import LogUtils


class EventFIFO(BaseFIFO):
    """
    事件队列
    """

    def push_value(self, value):
        """
        将事件推入事件队列
        """
        try:
            node = EventNode(value)
            super().push_value(node)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    def dispatch(self, topic, content, provider_name="default"):
        """
        将事件推入事件队列
        """
        node = EventNode({
            "topic": topic,
            "content": content,
            "provider_name": provider_name
        })
        super().push_value(node)

    def get_top(self):
        """
        获取事件队列的第一个事件
        """
        if self.size() > 0:
            return self._fifo[0]

    def has_event(self, event):
        """
        判断事件是否存在
        """
        return self._fifo.index(event) != -1

    def replace(self, event):
        """
        替换事件
        """
        index = self._fifo.index(event)
        if index != -1:
            self._fifo[index] = event
