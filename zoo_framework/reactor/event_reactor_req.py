import time
import uuid
from enum import Enum
from typing import Any


class ChannelType(Enum):
    """通道类型

    P1 任务：事件通道隔离
    """

    DEFAULT = "default"  # 默认通道
    SYSTEM = "system"  # 系统通道
    BUSINESS = "business"  # 业务通道
    LOG = "log"  # 日志通道
    ERROR = "error"  # 错误通道


class EventReactorReq:
    """事件响应器请求

    P1 任务实现：事件监听指定通道，防止不同通道的事件被误处理
    """

    topic: str
    content: Any
    channel: str
    reactor_name: str
    request_id: str
    request_time: float
    channel_type: ChannelType
    priority: int

    def __init__(
        self,
        topic: str,
        content: Any,
        reactor_name: str,
        channel: str = ChannelType.DEFAULT.value,
        priority: int = 0,
    ):
        """初始化事件请求

        Args:
            topic: 事件主题
            content: 事件内容
            reactor_name: 响应器名称
            channel: 通道名称（P1 任务：支持通道隔离）
            priority: 优先级
        """
        self.topic = topic
        self.content = content

        # P1 任务：事件监听指定通道，防止不同通道的事件被误处理
        self.channel = channel
        self.channel_type = self._get_channel_type(channel)

        self.reactor_name = reactor_name
        self.request_id = str(uuid.uuid1())
        self.request_time = time.time()
        self.priority = priority

    def _get_channel_type(self, channel: str) -> ChannelType:
        """根据通道名称获取通道类型

        Args:
            channel: 通道名称

        Returns:
            通道类型
        """
        try:
            return ChannelType(channel)
        except ValueError:
            return ChannelType.DEFAULT

    def match_channel(self, allowed_channels: list[str]) -> bool:
        """检查事件是否匹配允许的通道

        P1 任务：通道隔离验证

        Args:
            allowed_channels: 允许的通道列表

        Returns:
            是否匹配
        """
        return self.channel in allowed_channels

    def __repr__(self) -> str:
        return (
            f"EventReactorReq(topic={self.topic}, "
            f"channel={self.channel}, "
            f"reactor={self.reactor_name}, "
            f"priority={self.priority})"
        )


class ChannelManager:
    """通道管理器

    P1 任务：管理事件通道，实现通道隔离
    """

    def __init__(self):
        self._channels: dict[str, set[str]] = {}  # 通道 -> 主题集合
        self._reactor_channels: dict[str, list[str]] = {}  # 响应器 -> 通道列表

    def register_channel(self, channel: str, topics: list[str] | None = None) -> None:
        """注册通道

        Args:
            channel: 通道名称
            topics: 该通道支持的主题列表
        """
        if channel not in self._channels:
            self._channels[channel] = set()

        if topics:
            self._channels[channel].update(topics)

    def register_reactor_channels(self, reactor_name: str, channels: list[str]) -> None:
        """注册响应器监听的通道

        累加而非覆盖：同一个响应器可能被注册到多个通道（例如先经 `@event` 声明
        业务通道，再显式补充系统通道），覆盖会让先注册的通道静默失效。

        Args:
            reactor_name: 响应器名称
            channels: 监听的通道列表
        """
        allowed = self._reactor_channels.setdefault(reactor_name, [])
        for channel in channels:
            if channel not in allowed:
                allowed.append(channel)

    def is_channel_valid(self, channel: str) -> bool:
        """检查通道是否有效

        Args:
            channel: 通道名称

        Returns:
            是否有效
        """
        return channel in self._channels

    def can_handle_channel(self, reactor_name: str, channel: str) -> bool:
        """检查响应器是否监听指定通道

        这是通道判定的轻量入口：不构造事件请求对象，因而不会产生 UUID。
        分发热路径 MUST 使用本方法，而非构造完整请求后再判断。

        Args:
            reactor_name: 响应器名称
            channel: 通道名称

        Returns:
            是否监听该通道
        """
        allowed_channels = self._reactor_channels.get(reactor_name, [ChannelType.DEFAULT.value])
        return channel in allowed_channels

    def can_handle_event(self, reactor_name: str, event: EventReactorReq) -> bool:
        """检查响应器是否可以处理事件

        P1 任务：通道隔离验证

        Args:
            reactor_name: 响应器名称
            event: 事件请求

        Returns:
            是否可以处理
        """
        # 获取响应器监听的通道
        allowed_channels = self._reactor_channels.get(reactor_name, [ChannelType.DEFAULT.value])

        # 检查事件通道是否在允许列表中
        return event.match_channel(allowed_channels)

    def get_channel_topics(self, channel: str) -> set[str]:
        """获取通道支持的主题

        Args:
            channel: 通道名称

        Returns:
            主题集合
        """
        return self._channels.get(channel, set())


# 全局通道管理器
#
# 【已知欠债】模块级单例，**导入时即实例化**（非惰性），其 `_channels` / `_reactor_channels`
# 是进程级共享状态、须由测试单独复位（tests/conftest.py 的 _reset_registries）。
# 属容器外、未收编的载体；依据与判据见 specs/scoped-container 的
# 「框架自身的进程级共享 MUST 被显式归类」。
_channel_manager = ChannelManager()


def get_channel_manager() -> ChannelManager:
    """获取全局通道管理器"""
    return _channel_manager
