import threading
from typing import Any

from zoo_framework.core.aop import cage
from zoo_framework.utils import LogUtils
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

from .event_reactor import EventReactor
from .event_reactor_req import ChannelType, get_channel_manager


@cage
class EventReactorManager:
    """事件响应处理器.

    P1 任务：支持事件通道隔离
    """

    reactor_map = ThreadSafeDict()

    # 注册表的读-改-写需要整体互斥：ThreadSafeDict 只保护单次操作，
    # 无法阻止两个线程同时为同一主题创建列表。
    _registry_lock = threading.RLock()

    def __init__(self):
        from zoo_framework.params import EventParams

        # reactor_map 的值是"主题 -> 响应器列表"，必须展开后再逐个设置超时。
        # 直接对映射值调用 set_event_timeout 会在注册表非空时抛 AttributeError
        # （list 没有该方法），使响应器管理器在特定构造顺序下无法创建。
        for reactors in self.reactor_map.values():
            for reactor in reactors:
                reactor.set_event_timeout(EventParams.EVENT_JOIN_TIMEOUT)

    @classmethod
    def dispatch(cls, topic, content, reactor_name=None, channel: str = ChannelType.DEFAULT.value):
        """分发事件.

        把主题下、且通过通道校验的所有响应器逐个执行。单个响应器抛出的异常不会
        阻断其余响应器；主题下没有匹配的响应器时静默返回。

        Args:
            topic: 事件主题
            content: 事件内容
            reactor_name: 响应器名称；None 表示不过滤。历史默认哨兵值 "default"
                同样视为不过滤——它来自本方法的旧签名，且与 `get_reactor` 的
                "按名称过滤"参数语义冲突（过滤一个名为 default 的响应器必然匹配
                不到任何响应器）
            channel: 通道名称
        """
        name_filter = None if reactor_name in (None, "default") else [reactor_name]

        for reactor in cls.get_reactor(topic, name_filter, channel):
            try:
                reactor.execute(topic, content)
            except Exception as e:
                LogUtils.error(f"❌ Reactor '{reactor.reactor_name}' execution failed: {e}")

    @classmethod
    def get_reactor(
        cls, topic, reactor_names: list[str] | None = None, channel: str | None = None
    ) -> list[Any]:
        """获取事件处理器.

        P1 任务：支持按通道过滤事件处理器

        Args:
            topic: 事件主题
            reactor_names: 响应器名称列表
            channel: 通道名称（P1 新增）

        Returns:
            响应器列表
        """
        result = cls.reactor_map.get(topic)

        if result is None:
            return []

        # 复制一份再过滤：注册可能在其他线程进行，直接迭代原列表不安全
        filter_result = []
        for reactor in list(result):
            # P1：按名称过滤
            if reactor_names is not None and reactor.reactor_name not in reactor_names:
                continue

            # P1：按通道过滤
            if channel is not None and not cls._validate_channel(reactor.reactor_name, channel):
                continue

            filter_result.append(reactor)

        return filter_result

    @classmethod
    def _validate_channel(cls, reactor_name: str, channel: str) -> bool:
        """验证响应器是否可以处理该通道的事件.

        只做通道判断，不构造完整的事件请求对象——后者会为每个响应器生成一个 UUID，
        而本方法位于分发热路径上。

        Args:
            reactor_name: 响应器名称
            channel: 通道名称

        Returns:
            是否可以处理
        """
        return get_channel_manager().can_handle_channel(reactor_name, channel)

    @classmethod
    def register_reactor_channels(cls, reactor_name: str, channels: list[str]) -> None:
        """注册响应器监听的通道.

        P1 任务：支持通道隔离配置

        Args:
            reactor_name: 响应器名称
            channels: 监听的通道列表
        """
        channel_manager = get_channel_manager()
        channel_manager.register_reactor_channels(reactor_name, channels)
        LogUtils.info(f"✅ Reactor '{reactor_name}' registered to channels: {channels}")

    @classmethod
    def get_reactor_name_list(cls):
        """获取事件处理器名称列表."""
        return cls.reactor_map.get_keys()

    @classmethod
    def bind_topic_reactor(cls, topic: str, reactor: EventReactor) -> bool:
        """注册事件处理器.

        **幂等**：同一个响应器对象对同一主题重复注册时，该主题下的响应器集合保持
        不变——既不重复追加、也不修改已注册对象的名称。历史实现在这种情况下会重命名
        并追加，导致每构造一次调度器就在主题下多堆积一条记录，在进程内无限增长。

        这个方法可以被重写，以实现不同的事件注册方式，比如设置重试机制等.
        """
        with cls._registry_lock:
            reactors = cls.reactor_map.get(topic)
            if reactors is None:
                reactors = []
                cls.reactor_map[topic] = reactors

            if reactor in reactors:
                return True

            reactors.append(reactor)
            return True

    @classmethod
    def dispatch_by_channel(
        cls, topic: str, content: Any, channel: str = ChannelType.DEFAULT.value
    ) -> None:
        """按通道分发事件.

        P1 任务：支持按通道广播事件

        Args:
            topic: 事件主题
            content: 事件内容
            channel: 目标通道
        """
        channel_manager = get_channel_manager()

        # 获取该通道下所有的响应器
        all_reactors = []
        for reactor_name in cls.get_reactor_name_list():
            if channel_manager.can_handle_channel(reactor_name, channel):
                reactors = cls.get_reactor(topic, [reactor_name], channel)
                all_reactors.extend(reactors)

        # 执行所有匹配的响应器
        for reactor in all_reactors:
            try:
                reactor.execute(topic, content)
            except Exception as e:
                LogUtils.error(f"❌ Reactor '{reactor.reactor_name}' execution failed: {e}")
