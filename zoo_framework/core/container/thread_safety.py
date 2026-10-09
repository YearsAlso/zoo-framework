"""Thread-safety ownership declaration.

Sharing mutable objects across Workers is a footgun of concurrency, and the
old ``@cage`` was **completely silent** about it - yet what it shared was
exactly the stateful managers. This container therefore makes ownership a
**mandatory declaration at registration**: no implicit default is offered,
because implicitly defaulting to a safe assumption is precisely the breeding
ground for this class of defect.

The three values (see design D5):

- ``CONTAINER_SERIALIZED``: the container guarantees serialized access. Fits
  items that do no locking of their own but can accept serialization
- ``INSTANCE_GUARANTEED``: the instance guarantees it itself. Fits immutable
  items, or items with an internal lock
- ``SINGLE_THREAD``: single-thread scopes only. For items that are neither
  serialized nor self-guarding

The declaration is an **honest** assertion, not the container bailing the
instance out: writing ``INSTANCE_GUARANTEED`` on a lock-free mutable object
writes an unverified safety assumption into the code - worse than not
writing one.
"""


class ThreadSafety:
    """The legal values of thread-safety ownership."""

    CONTAINER_SERIALIZED = "container_serialized"
    INSTANCE_GUARANTEED = "instance_guaranteed"
    SINGLE_THREAD = "single_thread"

    ALL = (CONTAINER_SERIALIZED, INSTANCE_GUARANTEED, SINGLE_THREAD)

    DESCRIPTIONS = {
        CONTAINER_SERIALIZED: "serialized access guaranteed by the container",
        INSTANCE_GUARANTEED: "guaranteed by the instance itself",
        SINGLE_THREAD: "single-thread scopes only",
    }

    @classmethod
    def describe(cls, value: str) -> str:
        """Get the description for a value; unknown values return as-is."""
        return cls.DESCRIPTIONS.get(value, str(value))
