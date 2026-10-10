import time
import uuid
from enum import Enum
from typing import Any


class ChannelType(Enum):
    """Channel type.

    P1 task: event channel isolation.
    """

    DEFAULT = "default"  # default channel
    SYSTEM = "system"  # system channel
    BUSINESS = "business"  # business channel
    LOG = "log"  # log channel
    ERROR = "error"  # error channel


class EventReactorReq:
    """Event reactor request.

    P1 task implementation: events listen on a designated channel, so events
    of different channels are not handled by mistake.
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
        """Initialize the event request.

        Args:
            topic: the event topic
            content: the event content
            reactor_name: the reactor name
            channel: the channel name (P1 task: supports channel isolation)
            priority: the priority
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
        """Get the channel type by the channel name.

        Args:
            channel: the channel name

        Returns:
            The channel type
        """
        try:
            return ChannelType(channel)
        except ValueError:
            return ChannelType.DEFAULT

    def match_channel(self, allowed_channels: list[str]) -> bool:
        """Check whether the event matches the allowed channels.

        P1 task: channel isolation validation.

        Args:
            allowed_channels: the list of allowed channels

        Returns:
            Whether it matches
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
    """Channel manager.

    P1 task: manage event channels and implement channel isolation.
    """

    def __init__(self):
        self._channels: dict[str, set[str]] = {}  # channel -> topic set
        self._reactor_channels: dict[str, list[str]] = {}  # reactor -> channel list

    def register_channel(self, channel: str, topics: list[str] | None = None) -> None:
        """Register a channel.

        Args:
            channel: the channel name
            topics: the list of topics this channel supports
        """
        if channel not in self._channels:
            self._channels[channel] = set()

        if topics:
            self._channels[channel].update(topics)

    def register_reactor_channels(self, reactor_name: str, channels: list[str]) -> None:
        """Register the channels a reactor listens to.

        Accumulates instead of overwriting: the same reactor may be registered
        to several channels (e.g. first declared on a business channel via
        `@event`, then explicitly extended with the system channel);
        overwriting would silently invalidate the earlier registration.

        Args:
            reactor_name: the reactor name
            channels: the list of listened channels
        """
        allowed = self._reactor_channels.setdefault(reactor_name, [])
        for channel in channels:
            if channel not in allowed:
                allowed.append(channel)

    def is_channel_valid(self, channel: str) -> bool:
        """Check whether the channel is valid.

        Args:
            channel: the channel name

        Returns:
            Whether it is valid
        """
        return channel in self._channels

    def can_handle_channel(self, reactor_name: str, channel: str) -> bool:
        """Check whether the reactor listens on the channel.

        This is the lightweight entry for the channel decision: it builds no
        event request object, hence produces no UUID. The dispatch hot path
        MUST use this method instead of building a full request to decide.

        Args:
            reactor_name: the reactor name
            channel: the channel name

        Returns:
            Whether it listens on the channel
        """
        allowed_channels = self._reactor_channels.get(reactor_name, [ChannelType.DEFAULT.value])
        return channel in allowed_channels

    def can_handle_event(self, reactor_name: str, event: EventReactorReq) -> bool:
        """Check whether the reactor can handle the event.

        P1 task: channel isolation validation.

        Args:
            reactor_name: the reactor name
            event: the event request

        Returns:
            Whether it can handle the event
        """
        # Get the channels the reactor listens on
        allowed_channels = self._reactor_channels.get(reactor_name, [ChannelType.DEFAULT.value])

        # Check that the event channel is in the allowed list
        return event.match_channel(allowed_channels)

    def get_channel_topics(self, channel: str) -> set[str]:
        """Get the topics a channel supports.

        Args:
            channel: the channel name

        Returns:
            The topic set
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
    """Get the global channel manager."""
    return _channel_manager
