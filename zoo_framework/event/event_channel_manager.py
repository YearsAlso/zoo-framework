from zoo_framework.core.container import ThreadSafety, process_scoped
from zoo_framework.reactor import EventReactor

from ..fifo.node import EventNode
from .event_channel import EventChannel
from .event_channel_register import EventChannelRegister


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class EventChannelManager:
    """The event channel manager."""

    _event_channel_register: EventChannelRegister = EventChannelRegister()

    @classmethod
    def refresh_channel(cls, channel_name, topic, reactor: EventReactor):
        """Refresh an event channel."""
        channel: EventChannel = cls._event_channel_register.register(channel_name)
        channel.register_reactor(topic, reactor)

    @classmethod
    def get_channel(cls, channel_name) -> EventChannel:
        """Get an event channel."""
        return cls._event_channel_register.get_channel(channel_name)

    @classmethod
    def get_channel_register(cls):
        """Get the channel registrar."""
        return cls._event_channel_register

    @classmethod
    def get_all_channel_name(cls):
        """Get all channel names."""
        return cls._event_channel_register.get_channel_name_list()

    @classmethod
    def get_all_channel_count(cls):
        """Get the channel count."""
        return cls._event_channel_register.get_channel_count()

    @classmethod
    def perform_event(cls, event: EventNode):
        """Dispatch an event."""
        channel: EventChannel = cls._event_channel_register.get_channel(event.channel_name)

        # Get all reactors, then put the event into the queue
        if channel is None:
            raise Exception("channel not found")
        # Get the response strategy
        reactors: list[EventReactor]
        if event.response_mechanism == 1:
            # Take the first reactor
            reactors = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                reactors[0].execute(event.topic, event.content)
        elif event.response_mechanism == 2:
            # Get reactors by event priority
            reactors = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                for reactor in reactors:
                    reactor.execute(event.topic, event.content)
        elif event.response_mechanism == 3:
            # Take all reactors
            reactors = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                for reactor in reactors:
                    reactor.execute(event.topic, event.content)
        elif event.response_mechanism == 4:
            # Take all reactors
            reactors = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                # Get the reactor by name
                for reactor in reactors:
                    if reactor.reactor_name == event.reactor_name:
                        reactor.execute(event.topic, event.content)

    @classmethod
    def get_channel_reactors(cls, event: EventNode) -> list[EventReactor] | None:
        """Get the event reactors of the channel."""
        # Resolve the event's channel
        channel: EventChannel = cls._event_channel_register.get_channel(event.channel_name)

        # Get all reactors, then put the event into the queue
        if channel is None:
            # The `return None` after `raise` was dead (proven by type
            # checking) and has been removed.
            raise Exception("channel not found")

        # Get the response strategy
        reactors: list[EventReactor]
        if event.response_mechanism == 1:
            # Take the first reactor
            reactors = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                return [reactors[0]]
        elif event.response_mechanism == 2:
            # Get reactors by event priority
            reactors = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                # Sort by combined priority, high to low: EventNode's existing
                # comment says "higher priority responds first". Must use sorted
                # rather than list.sort - the latter sorts in place and returns
                # None.
                return sorted(reactors, key=lambda x: x.get_priority(), reverse=True)
        elif event.response_mechanism == 3:
            # Take all reactors
            reactors = channel.get_reactors(event.topic)
            return reactors
        elif event.response_mechanism == 4:
            # Take all reactors
            reactors = channel.get_reactors(event.topic)
            if reactors is not None and len(reactors) > 0:
                # Get the reactor by name
                for reactor in reactors:
                    if reactor.reactor_name == event.reactor_name:
                        return [reactor]
        return []
