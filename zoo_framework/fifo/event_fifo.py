from .node import EventFIFONode
from zoo_framework.fifo import BaseFIFO
from zoo_framework.utils import LogUtils


class EventFIFO(BaseFIFO):

    def push_value(self, value):
        try:
            node = EventFIFONode(value)
            super().push_value(node)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    def dispatch(self, topic, content, handler_name="default"):
        node = EventFIFONode({
            "topic": topic,
            "content": content,
            "handler_name": handler_name
        })
        super().push_value(node)
