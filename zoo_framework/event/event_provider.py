from zoo_framework.core.aop import cage
from zoo_framework.event import EventChannel, EventChannelRegister
from zoo_framework.fifo.node import EventNode


@cage
class EventProvider:
    """事件提供器."""

    _eventChannelRegister = EventChannelRegister()

    def push(self, event: EventNode):
        channel = self._eventChannelRegister.get_channel(event.channel_name)
        if channel:
            channel.push_event(event)
        else:
            # 事件通道不存在，说明没有响应器
            raise Exception("channel not found")

    def refresh(self, event: EventNode):
        """刷新事件."""
        channel: EventChannel = self._eventChannelRegister.get_channel(event.channel_name)
        if channel:
            # 通道中是否存在该事件
            channel.refresh_event(event)
        else:
            # 事件通道不存在，说明没有响应器
            raise Exception("channel not found")
