from zoo_framework.fifo import EventFIFO
from zoo_framework.utils import LogUtils


class EventProvider:
    """
    事件提供者
    """
    _event_fifo: EventFIFO = EventFIFO()

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
    def dispatch(cls, topic, content, handler_name="default"):
        """
        将事件推入事件队列
        """
        cls._event_fifo.dispatch(topic, content, handler_name)
