from zoo_framework.utils import LogUtils

from .base_fifo import BaseFIFO
from .node import EventNode


class EventFIFO(BaseFIFO[EventNode]):
    """The event queue."""

    def push_value(self, value):
        """Push an event into the event queue."""
        try:
            if isinstance(value, dict):
                node = EventNode(**value)
            elif isinstance(value, EventNode):
                node = value
            else:
                # For values that are neither dict nor EventNode, create a
                # default event node
                node = EventNode(topic="default", content=str(value))
            super().push_value(node)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    def dispatch(self, topic, content, provider_name="default"):
        """Push an event into the event queue.

        Note: `provider_name` MUST be written onto the event's
        `channel_name` - it decides which channel queue the event belongs
        to; dropping it would land all events on the default channel and
        channel isolation would break.
        """
        node = EventNode(topic=topic, content=content, channel_name=provider_name)
        super().push_value(node)

    def get_top(self) -> EventNode | None:
        """Get the first event of the event queue."""
        if self.size() > 0:
            return self._fifo[0]
        return None

    def has_event(self, event):
        """Whether the event exists.

        Membership check is required: `list.index()` raises `ValueError` on
        a miss rather than returning -1, and the normal path of this
        method's callers (`EventChannel.refresh_event`,
        `EventProvider.refresh`) is exactly "do nothing on a miss".
        """
        return event in self._fifo

    def replace(self, event):
        """Replace the event; do nothing when it does not exist."""
        if event not in self._fifo:
            return
        self._fifo[self._fifo.index(event)] = event
