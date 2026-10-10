from zoo_framework.core.container import ThreadSafety, process_instance, process_scoped
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

from .event_channel import EventChannel


class _ChannelMapProxyMeta(type):
    """Class-level read proxy for `_channel_map` (absorb-debt-carriers / #50
    deliverable 1, option A).

    Same shape as ``EventReactorManager``'s registry: the state drops to a
    process-level instance attribute so a container reset resets it
    completely; the metaclass exists only to keep the existing class-level
    read / whole-table-replacement call style working.
    """

    @property
    def _channel_map(cls) -> ThreadSafeDict:
        # Same as EventReactorManager: container resolution always returns
        # an instance of this class; the ignore covers the Any signature,
        # not an unverified premise
        return process_instance(cls)._channel_map  # type: ignore[no-any-return]

    @_channel_map.setter
    def _channel_map(cls, value: ThreadSafeDict) -> None:
        # Backward-compatible with the legacy reset style (whole-table
        # replacement): semantics forward to the process-level instance. New
        # code SHOULD use the container reset / this instance's clear().
        process_instance(cls)._channel_map = value


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class EventChannelRegister(metaclass=_ChannelMapProxyMeta):
    """The event channel registrar.

    Registry ownership (absorb-debt-carriers / #50): `_channel_map` is state
    of the **process-level instance** (this class is registered into the
    framework container via `process_scoped`), no longer a class attribute;
    the previously self-declared [known debt] is lifted by the absorption.
    The historical dead attributes `_single` / `_instance` (legacy singleton
    markers with zero reads or writes repo-wide) are removed with it.
    """

    def __init__(self):
        # The event channel map: instance state, empty at construction;
        # rebuilt on first resolution after a container reset.
        self._channel_map: ThreadSafeDict[str, EventChannel] = ThreadSafeDict()

    @classmethod
    def register(cls, channel_name):
        # get_channel creates in place on a miss and returns, so it never
        # returns None - the original None branch was therefore dead code
        # (proven by type checking) and has been removed. register and
        # get_channel now share one semantics.
        return cls.get_channel(channel_name)

    @classmethod
    def unregister(cls, channel_name):
        cls._channel_map.pop(channel_name)

    @classmethod
    def get_channel(cls, channel_name) -> EventChannel:
        # Use `__getitem__` (returns a non-Optional V) rather than `get()`
        # (returns V | None): on a miss the channel is created in place
        # first, so a value always exists here and no narrowing or cast is
        # needed on the type level.
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
