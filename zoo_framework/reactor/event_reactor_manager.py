import threading
from typing import Any

from zoo_framework.core.container import ThreadSafety, process_instance, process_scoped
from zoo_framework.utils import LogUtils
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

from .event_reactor import EventReactor
from .event_reactor_req import ChannelType, get_channel_manager


class _ReactorMapProxyMeta(type):
    """类级 `reactor_map` 读代理（变更 absorb-debt-carriers / #50 交付 1，方案 A）.

    注册表状态已降为**进程级实例属性**——容器 reset 天然带走，conftest 不再单独
    复位类属性。本元类只为**类级读取**（`EventReactorManager.reactor_map`）保提供
    入口：它转发到进程级实例的同名属性。实例属性查找不经过元类，`self.reactor_map`
    仍是普通实例属性；既有 classmethod 的 `cls.reactor_map` 写法零改动。
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
    """事件响应处理器.

    P1 任务：支持事件通道隔离

    注册表归属（变更 absorb-debt-carriers / #50）：`reactor_map` 是**进程级实例**的
    状态（本类经 `process_scoped` 登记于框架容器），不再是类属性——线程安全声明
    `INSTANCE_GUARANTEED` 至此与实现一致；容器复位即完全复位。
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
            # 超时在登记现场设置（取代原"构造时遍历刷新"兜底——注册表降为实例态后，
            # 首次构造必为空表，遍历只能空转）
            from zoo_framework.params import EventParams

            reactor.set_event_timeout(EventParams.EVENT_JOIN_TIMEOUT)
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
