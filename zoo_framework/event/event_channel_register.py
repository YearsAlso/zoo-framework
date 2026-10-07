from zoo_framework.core.container import ThreadSafety, process_instance, process_scoped
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

from .event_channel import EventChannel


class _ChannelMapProxyMeta(type):
    """类级 `_channel_map` 读代理（变更 absorb-debt-carriers / #50 交付 1，方案 A）.

    与 ``EventReactorManager`` 的注册表同形态：状态降为进程级实例属性，容器复位即
    完全复位；元类只为类级读取/整表替换的既有写法提供入口。
    """

    @property
    def _channel_map(cls) -> ThreadSafeDict:
        # 同 EventReactorManager：容器解析必返本类实例，ignoring 的是 Any 签名而非未验证前提
        return process_instance(cls)._channel_map  # type: ignore[no-any-return]

    @_channel_map.setter
    def _channel_map(cls, value: ThreadSafeDict) -> None:
        # 兼容旧复位写法（整表替换）：语义转发到进程级实例。新代码 SHOULD 用
        # 容器 reset / 本实例 clear()。
        process_instance(cls)._channel_map = value


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class EventChannelRegister(metaclass=_ChannelMapProxyMeta):
    """事件通道注册器.

    注册表归属（变更 absorb-debt-carriers / #50）：`_channel_map` 是**进程级实例**
    的状态（本类经 `process_scoped` 登记于框架容器），不再是类属性；原先自标的
    【已知欠债】随收编解除。历史死属性 `_single` / `_instance`（全仓库零读写的
    遗留单例标记）一并删除。
    """

    def __init__(self):
        # 事件通道字典：实例状态，新建即空表；容器 reset 后首次解析重建。
        self._channel_map: ThreadSafeDict[str, EventChannel] = ThreadSafeDict()

    @classmethod
    def register(cls, channel_name):
        # get_channel 在未命中时就地创建再返回，故**不会**返回 None——原先的 None 分支
        # 因此是死代码（类型检查已证），已删。register 与 get_channel 现为同一语义。
        return cls.get_channel(channel_name)

    @classmethod
    def unregister(cls, channel_name):
        cls._channel_map.pop(channel_name)

    @classmethod
    def get_channel(cls, channel_name) -> EventChannel:
        # 用 `__getitem__`（返回非 Optional 的 V）而不是 `get()`（返回 V | None）：
        # 未命中时先就地创建，故此处必有值，类型上也就不需要收窄或 cast。
        if channel_name not in cls._channel_map:
            cls._channel_map[channel_name] = EventChannel(channel_name)
        return cls._channel_map[channel_name]  # type: ignore[no-any-return]  # ThreadSafeDict.__getitem__ 经容器路径推为 Any

    @classmethod
    def get_all_channel(cls):
        return cls._channel_map.get_values()

    @classmethod
    def get_channel_name_list(cls):
        return cls._channel_map.get_keys()

    @classmethod
    def get_channel_count(cls):
        return len(cls._channel_map)
