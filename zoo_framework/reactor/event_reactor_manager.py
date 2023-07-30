import uuid
from typing import Any, List

from .event_reactor import EventReactor
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict
from zoo_framework.core.aop import cage


@cage
class EventReactorManager:
    """
    事件响应处理器
    """
    reactor_map = ThreadSafeDict()

    # 自动重命名
    auto_rename = True

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
        reactor.execute(topic, content)

    @classmethod
    def get_reactor(cls, topic, reactor_names: list[str] = None) -> list[Any]:
        """
        获取事件处理器
        """
        # TODO: 事件监听指定通道，防止不同通道的事件被误处理
        result = cls.reactor_map.get(topic)
        if reactor_names is None:
            return result

        if result is None:
            return []

        filter_result = []
        for reactor in result:
            if reactor_names.index(reactor.reactor_name) != -1:
                filter_result.append(reactor)

        return filter_result

    @classmethod
    def get_reactor_name_list(cls):
        """
        获取事件处理器名称列表
        """
        return cls.reactor_map.get_keys()

    @classmethod
    def auto_rename_reactor(cls, reactor: EventReactor):
        """
        自动重命名事件处理器
        """
        reactor.reactor_name = reactor.reactor_name + "_" + uuid.uuid4().__str__()

    @classmethod
    def bind_topic_reactor(cls, topic: str, reactor: EventReactor) -> bool:
        """
        注册事件处理器
        这个方法可以被重写，以实现不同的事件注册方式，比如设置重试机制等
        """
        # 如果自动重命名，则自动重命名
        if cls.reactor_map.get(topic) is None:
            cls.reactor_map[topic] = []

        # 如果名称已经存在，则不注册

        # 寻找是否已经存在
        if reactor in cls.reactor_map[topic]:
            # 判断重命名策略
            if cls.auto_rename is False:
                return False
            cls.auto_rename_reactor(reactor)
            cls.reactor_map[topic].append(reactor)
            return True

        cls.reactor_map[topic].append(reactor)
        return True
