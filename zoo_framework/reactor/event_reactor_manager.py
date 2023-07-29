from .event_reactor import EventReactor
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict
from zoo_framework.core.aop import cage


@cage
class EventReactorManager:
    """
    事件响应处理器
    """
    reactor_map = ThreadSafeDict()

    def __init__(self):
        for key, value in self.reactor_map.items():
            from zoo_framework.params import EventParams
            value.set_event_timeout(EventParams.EVENT_JOIN_TIMEOUT)

    @classmethod
    def dispatch(cls, topic, content, reactor_name="default"):
        """
        分发事件
        """
        reactor = cls.get_reactor(reactor_name)
        reactor.execute(topic, content, reactor_name)

    @classmethod
    def get_reactor(cls, reactor_name="default", channel_name="all"):
        """
        获取事件处理器
        """
        # TODO: 事件监听指定通道，防止不同通道的事件被误处理
        return cls.reactor_map.get(reactor_name)

    @classmethod
    def register(cls, reactor_name: str, callback, error_callback=None):
        """
        注册事件处理器
        这个方法可以被重写，以实现不同的事件注册方式，比如设置重试机制等
        """
        # 创建一个事件响应器
        reactor = EventReactor(reactor_name)

        # 设置事件调用方法
        reactor.set_event_callback(callback)

        # 设置错误处理方法
        reactor.set_error_callback(error_callback)

        # 设置超时时间
        cls.reactor_map[reactor_name] = reactor
