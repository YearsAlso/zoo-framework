from zoo_framework.core.container import ThreadSafety, process_scoped
from zoo_framework.event import EventChannel, EventChannelRegister
from zoo_framework.fifo.node import EventNode


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class EventProvider:
    """The event provider."""

    _eventChannelRegister = EventChannelRegister()

    def push(self, event: EventNode):
        channel = self._eventChannelRegister.get_channel(event.channel_name)
        if channel:
            channel.push_event(event)
        else:
            # The channel does not exist, meaning no reactor was bound
            raise Exception("channel not found")

    def refresh(self, event: EventNode):
        """Refresh an event."""
        channel: EventChannel = self._eventChannelRegister.get_channel(event.channel_name)
        if channel:
            # Whether the event already exists in the channel
            channel.refresh_event(event)
        else:
            # The channel does not exist, meaning no reactor was bound
            raise Exception("channel not found")
