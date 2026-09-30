from zoo_framework.core.container import ThreadSafety, process_scoped
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

from .event_channel import EventChannel


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class EventChannelRegister:
    """事件通道注册器."""

    _single = None
    _instance = None

    # 事件通道字典
    # 【已知欠债】类属性即进程级共享状态，且属**尚未收编**的容器外载体：容器只持有本类的
    # **实例**，够不到这个类属性，故 tests/conftest.py 必须单独复位它。依据见
    # specs/scoped-container 的「框架自身的进程级共享 MUST 被显式归类」。
    _channel_map: ThreadSafeDict[str, EventChannel] = ThreadSafeDict()

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
        return cls._channel_map[channel_name]

    @classmethod
    def get_all_channel(cls):
        return cls._channel_map.get_values()

    @classmethod
    def get_channel_name_list(cls):
        return cls._channel_map.get_keys()

    @classmethod
    def get_channel_count(cls):
        return len(cls._channel_map)
