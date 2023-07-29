from .node import EventFIFONode
from zoo_framework.fifo import BaseFIFO
from zoo_framework.utils import LogUtils


class EventFIFO(BaseFIFO):

    def push_value(self, value):
        """
        将事件推入事件队列
        """
        try:
            node = EventFIFONode(value)
            super().push_value(node)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    def dispatch(self, topic, content, provider_name="default"):
        """
        将事件推入事件队列
        """
        node = EventFIFONode({
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
