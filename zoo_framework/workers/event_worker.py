from concurrent.futures import Future, ThreadPoolExecutor, wait
from functools import partial
from typing import TYPE_CHECKING

from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker

if TYPE_CHECKING:
    from zoo_framework.event import EventChannel
    from zoo_framework.fifo.node import EventNode


class EventWorker(BaseWorker):
    """Event Worker.

    The key constraint of the consume loop: every event taken from the
    queue MUST have a settled destination - delivered, requeued, or moved to
    dead-letter. Silent dropping was historically this class's main source of
    event loss.

    Note: this class MUST NOT be decorated with any class-replacing decorator
    (the historical `@cage` did exactly that and was deleted).
    `WorkerRegistry.register_class` validates the contract with `issubclass`;
    swapping the class for a function would make it raise
    `TypeError: issubclass() arg 1 must be a class`. The singleton and the
    instance cache are owned by `WorkerRegistry._worker_instances`, with no
    second mechanism needed - so this class also does not take
    `@process_scoped`: that would move the "one instance per Worker"
    ownership away from `WorkerRegistry`.
    """

    def __init__(self):
        # EventParams is imported lazily and must precede the props assembly:
        # the tempo participates in BaseWorker.__init__.
        # Resolution happens at first import; freezing into the defaults
        # would occur if it were earlier than the config load (see #51) -
        # this class is constructed by WorkerRegistry at runtime, so the
        # order holds.
        from zoo_framework.params import EventParams

        # is_loop is exposed by BaseWorker as a property with _props as the
        # sole source of truth; here it MUST NOT be shadowed by an instance
        # attribute (the property has no setter, assignment raises
        # AttributeError directly).
        BaseWorker.__init__(
            self,
            {
                "is_loop": True,
                "delay_time": EventParams.EVENT_DELAY_TIME,
                "name": "EventWorker",
            },
        )

        # Event channel manager
        self.eventChannelManager: EventChannelManager = EventChannelManager()

        # Reactor dispatch executor: built once per instance
        # (align-execution-primitives D1). Replaces the historical
        # gevent.spawn/joinall: greenlet primitives are unavailable on
        # free-threaded builds, and a single dispatch measured 38.1 us, far
        # above a thread submit.
        self._executor = ThreadPoolExecutor(
            max_workers=EventParams.EVENT_EXECUTOR_WORKERS,
            thread_name_prefix="zoo-event-reactor",
        )
        # The destroy path is invoked via BaseWorker.__del__; wait=False
        # matches the greenlet era: no forced kill and no unbounded wait for
        # in-flight reactors.
        self._destroy_func = partial(self._executor.shutdown, wait=False, cancel_futures=True)

    def _execute(self):
        from zoo_framework.params import EventParams

        channel_names = self.eventChannelManager.get_all_channel_name()
        dispatched: list[Future] = []
        # TODO: get all event channels except failed ones
        for channel_name in channel_names:
            # get_channel creates-and-returns in place on a miss, so it will **never** return None;
            # the old `if channel is None: continue` was therefore dead code (proven by type checking) and was removed.
            channel: EventChannel = self.eventChannelManager.get_channel(channel_name)
            # Get all the event channels
            # This round only consumes events already queued at round start: requeued events wait for the next round,
            # otherwise the retry quota is exhausted within one consume loop and retrying is void.
            pending = channel.size()
            while pending > 0:
                pending -= 1
                event_node: EventNode | None = channel.pop_value()
                # A race window exists between size() and pop_value(): a concurrent producer may take elements in between.
                # An empty pop means no events this round; the loop must end - any method call on None raises.
                if event_node is None:
                    break
                # Decide whether the event is expired
                if event_node.is_expire():
                    event_node.expire_callback()
                    continue
                # Get the event reactors
                try:
                    reactors = self.eventChannelManager.get_channel_reactors(event_node)
                except Exception as e:
                    # The event was already popped; the exception path also needs a settled destination
                    channel.push_dead_letter(event_node, reason=f"failed to look up reactors: {e}")
                    continue
                # If empty here, check the node's retry quota; with quota left it must go back to the queue.
                # `not reactors` covers both None and []: get_channel_reactors returns
                # `list[EventReactor] | None`, where None means "no matching reactor", same as an
                # empty list. (This used to be written len(reactors) == 0, with a None-triggered
                # TypeError caught by the except above - exceptions as control flow, misreporting
                # "no match" as "failed to look up reactors".)
                if not reactors:
                    self._requeue_or_dead_letter(channel, event_node, reason="no matching reactor")
                    continue
                for reactor in reactors:
                    # Run the event reactor: EventReactor's public entry is execute(topic, content).
                    f = self._executor.submit(reactor.execute, event_node.topic, event_node.content)
                    dispatched.append(f)

        if len(dispatched) > 0:
            # A bounded wait for this round's dispatch results; timeouts and exceptions both go to observable reporting
            wait(dispatched, timeout=EventParams.EVENT_JOIN_TIMEOUT)
            self._report_unfinished(dispatched)

    @staticmethod
    def _requeue_or_dead_letter(channel, event_node, reason: str = "") -> None:
        """The settled destination when an event cannot be delivered.

        With retry quota left, decrement it and requeue; otherwise move to
        dead-letter - both paths are observable, no silent dropping.

        Args:
            channel: the channel the event belongs to
            event_node: the event that could not be delivered
            reason: the reason it could not be delivered
        """
        remaining = event_node.get_retry_times()
        if remaining > 0:
            event_node.set_retry_times(remaining - 1)
            channel.push_event(event_node)
            return

        channel.push_dead_letter(event_node, reason=reason)

    @staticmethod
    def _report_unfinished(dispatched: list[Future]) -> None:
        """Report reactors still running past the join timeout, and exceptions carried by finished reactors.

        The results of ones unfinished at timeout are not collected and MUST
        be observable, not silently vanish with the timeout; exceptions
        carried by finished ones MUST NOT be swallowed (in the greenlet era
        they vanished silently).

        Args:
            dispatched: all futures dispatched in this round
        """
        unfinished = [f for f in dispatched if not f.done()]
        if unfinished:
            LogUtils.warning(
                f"{len(unfinished)} reactors were still running after the join timeout; their results were not collected",
                "EventWorker",
            )

        for f in dispatched:
            if not f.done():
                continue
            # After done(), exception() does not block; None when no exception was raised.
            exc = f.exception()
            if exc is not None:
                LogUtils.warning(
                    f"a reactor raised and its result was not collected: {exc!r}", "EventWorker"
                )
