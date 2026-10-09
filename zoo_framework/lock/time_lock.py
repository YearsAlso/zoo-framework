from .base_lock import BaseLock


class TimeLock(BaseLock):
    """A count-gated permit holder (same semantics as CountLock).

    Historical note: this class's old docstring claimed timeout and callback
    semantics, but the implementation never provided a timeout clock or any
    callback invocation - the ``callback`` taken by ``__init__`` was only
    stored, never called, and ``timeout`` actually behaves as the remaining
    permit count being decremented. Described here as the actual behavior,
    keeping documentation faithful to the implementation.

    Note: like ``CountLock``, this class overrides ``acquire`` / ``release``,
    so it provides **neither mutual exclusion nor thread safety**, and the
    lock held by ``BaseLock`` is not actually used. It only fits permit
    counting within a single thread.
    """

    def __init__(self, timeout=1, callback=None):
        """Initialize the count gate.

        Args:
            timeout: the remaining permit count (the parameter name follows
                history; the semantics are actually a count)
            callback: a legacy parameter; the current implementation never
                calls it
        """
        super().__init__()
        self._timeout = timeout
        self._callback = callback

    def acquire(self, blocking=True, timeout=-1):
        """Try to spend one permit.

        Returns:
            True when quota remains, False otherwise
        """
        if self._timeout > 0:
            self._timeout -= 1
            return True
        return False

    def release(self):
        """Return one permit."""
        self._timeout += 1
        return True

    def __str__(self):
        return f"TimeLock(timeout={self._timeout})"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return id(self) == id(other)

    def __ne__(self, other):
        return id(self) != id(other)

    def __lt__(self, other):
        return id(self) < id(other)

    def __le__(self, other):
        return id(self) <= id(other)

    def __gt__(self, other):
        return id(self) > id(other)

    def __ge__(self, other):
        return id(self) >= id(other)
