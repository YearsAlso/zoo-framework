from .node import EventFIFONode
from zoo_framework.fifo import BaseFIFO
from zoo_framework.utils import LogUtils


class EventFIFO(BaseFIFO):
    @classmethod
    def push_value(cls, value):
        try:
            node = EventFIFONode(value)
            super().push_value(node)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)
    
    @classmethod
    def dispatch(cls, topic, content, handler_name="default"):
        node = EventFIFONode({
            "topic": topic,
            "content": content,
            "handler_name": handler_name
        })
        super().push_value(node)
