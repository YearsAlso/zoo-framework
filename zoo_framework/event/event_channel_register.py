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
    _channel_map: ThreadSafeDict = ThreadSafeDict()

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
        if channel_name not in cls._channel_map:
            # 创建事件通道
            from zoo_framework.event.event_channel import EventChannel

            cls._channel_map[channel_name] = EventChannel(channel_name)
            return cls._channel_map.get(channel_name)
        return cls._channel_map.get(channel_name)

    @classmethod
    def get_all_channel(cls):
        return cls._channel_map.get_values()

    @classmethod
    def get_channel_name_list(cls):
        return cls._channel_map.get_keys()

    @classmethod
    def get_channel_count(cls):
        return len(cls._channel_map)
