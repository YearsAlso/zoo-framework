import threading
from typing import Any

from zoo_framework.core.container import ThreadSafety, process_instance, process_scoped
from zoo_framework.utils import LogUtils
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

from .event_reactor import EventReactor
from .event_reactor_req import ChannelType, get_channel_manager


class _ReactorMapProxyMeta(type):
    """Class-level `reactor_map` read proxy (change absorb-debt-carriers / #50 deliverable 1, option A).

    The registry state has been downgraded to a **process-level instance
    attribute** - a container reset takes it away naturally, so conftest no
    longer resets a class attribute separately. This metaclass exists only to
    keep the **class-level read** entry point
    (`EventReactorManager.reactor_map`): it forwards to the process-level
    instance's attribute of the same name. Instance attribute lookup does not
    go through the metaclass, so `self.reactor_map` is still a plain instance
    attribute; existing classmethods that read `cls.reactor_map` are unchanged.
    """

    @property
    def reactor_map(cls) -> ThreadSafeDict:
        # 容器按 cls 注册（工厂即类本身），解析必返本类实例；
        # 压制的是 resolve 的 Any 签名，不是未验证的假设。
        return process_instance(cls).reactor_map  # type: ignore[no-any-return]

    @reactor_map.setter
    def reactor_map(cls, value: ThreadSafeDict) -> None:
        # 兼容旧复位写法（整表替换）：语义转发到进程级实例。新代码 SHOULD 用
        # 容器 reset / 本实例 clear()。
        process_instance(cls).reactor_map = value


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class EventReactorManager(metaclass=_ReactorMapProxyMeta):
    """Event reactor manager.

    P1 task: event channel isolation.

    Registry ownership (change absorb-debt-carriers / #50): `reactor_map` is
    the state of the **process-level instance** (this class is registered in
    the framework container via `process_scoped`), no longer a class
    attribute - the `INSTANCE_GUARANTEED` thread-safety declaration is thereby
    faithful to the implementation; a container reset resets it fully.
    """

    # 注册表的读-改-写需要整体互斥：ThreadSafeDict 只保护单次操作，
    # 无法阻止两个线程同时为同一主题创建列表。锁留在类级：全进程只有一个
    # 实例（process_scoped），类级锁与实例级锁同粒度，且 classmethod 可直接引用。
    _registry_lock = threading.RLock()

    def __init__(self):
        from zoo_framework.params import EventParams

        # 注册表是实例状态：新建即空表。保留对已有条目的超时刷新（同一实例被
        # 重复"构造"时 __init__ 已被幂等守卫拦下，这里只会见到首次的空表）；
        # 新注册项的超时改由 bind_topic_reactor 在登记现场设置。
        self.reactor_map: ThreadSafeDict[str, list[EventReactor]] = ThreadSafeDict()
        for reactors in self.reactor_map.values():
            for reactor in reactors:
                reactor.set_event_timeout(EventParams.EVENT_JOIN_TIMEOUT)

    @classmethod
    def dispatch(cls, topic, content, reactor_name=None, channel: str = ChannelType.DEFAULT.value):
        """Dispatch an event.

        Executes each reactor under the topic that passes the channel
        validation. An exception raised by one reactor does not block the
        others; returns silently when no reactor matches the topic.

        Args:
            topic: the event topic
            content: the event content
            reactor_name: the reactor name; None means no filtering. The
                legacy sentinel value "default" is also treated as no
                filtering - it comes from this method's old signature and
                conflicts with `get_reactor`'s "filter by name" semantics
                (filtering a reactor named default can never match anything)
            channel: the channel name
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
        """Get the event reactors.

        P1 task: filter event reactors by channel.

        Args:
            topic: the event topic
            reactor_names: the reactor name list
            channel: the channel name (added in P1)

        Returns:
            The reactor list
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
        """Check whether a reactor may handle events of the channel.

        Only performs the channel check and does not build a full event
        request object - the latter would generate a UUID per reactor, and
        this method sits on the dispatch hot path.

        Args:
            reactor_name: the reactor name
            channel: the channel name

        Returns:
            Whether it may handle the channel
        """
        return get_channel_manager().can_handle_channel(reactor_name, channel)

    @classmethod
    def register_reactor_channels(cls, reactor_name: str, channels: list[str]) -> None:
        """Register the channels a reactor listens to.

        P1 task: channel isolation configuration.

        Args:
            reactor_name: the reactor name
            channels: the list of listened channels
        """
        channel_manager = get_channel_manager()
        channel_manager.register_reactor_channels(reactor_name, channels)
        LogUtils.info(f"✅ Reactor '{reactor_name}' registered to channels: {channels}")

    @classmethod
    def get_reactor_name_list(cls):
        """Get the event reactor name list."""
        return cls.reactor_map.get_keys()

    @classmethod
    def bind_topic_reactor(cls, topic: str, reactor: EventReactor) -> bool:
        """Register an event reactor.

        **Idempotent**: when the same reactor object is registered for the
        same topic repeatedly, the reactor set under the topic stays
        unchanged - neither appended again nor renamed. The legacy
        implementation renamed and appended in that case, so each scheduler
        construction piled one more record under the topic and grew without
        bound within the process.

        This method may be overridden to implement different event
        registration styles, e.g. adding a retry mechanism.
        """
        with cls._registry_lock:
            reactors = cls.reactor_map.get(topic)
            if reactors is None:
                reactors = []
                cls.reactor_map[topic] = reactors

            if reactor in reactors:
                return True

            reactors.append(reactor)
            # 超时在登记现场设置（取代原"构造时遍历刷新"兜底——注册表降为实例态后，
            # 首次构造必为空表，遍历只能空转）
            from zoo_framework.params import EventParams

            reactor.set_event_timeout(EventParams.EVENT_JOIN_TIMEOUT)
            return True

    @classmethod
    def dispatch_by_channel(
        cls, topic: str, content: Any, channel: str = ChannelType.DEFAULT.value
    ) -> None:
        """Dispatch an event by channel.

        P1 task: broadcast events by channel.

        Args:
            topic: the event topic
            content: the event content
            channel: the target channel
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
