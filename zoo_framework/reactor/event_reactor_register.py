from zoo_framework.utils.thread_safe_dict import ThreadSafeDict
from zoo_framework.core.aop import cage


@cage
class EventReactorRegister:
    """
    事件响应处理器
    """
    handler_map = ThreadSafeDict()

    def __init__(self):
        for key, value in self.handler_map.items():
            from zoo_framework.params import EventParams
            value.set_event_timeout(EventParams.EVENT_JOIN_TIMEOUT)

    @classmethod
    def dispatch(cls, topic, content, handler_name="default"):
        """
        分发事件
        """
        handler = cls.get_handler(handler_name)
        handler.handle(topic, content, handler_name)

    @classmethod
    def get_handler(cls, handler_name="default"):
        """
        获取事件处理器
        """
        return cls.handler_map.get(handler_name)

    @classmethod
    def register(cls, handler_name: str, handler):
        """
        注册事件处理器
        """
        cls.handler_map[handler_name] = handler
