from .base_lock import BaseLock


class CountLock(BaseLock):
    """A count gate admitting by remaining permits.

    With capacity N, the first N ``acquire`` calls succeed and the N+1st
    fails; each ``release`` returns one permit.

    Note: this class overrides ``acquire`` / ``release``, so it provides
    **neither mutual exclusion nor thread safety** (the read-modify-write of
    ``self._count`` is not atomic) and the lock held by ``BaseLock`` is in
    fact never used. It only fits permit counting within a single thread.
    """

    def __init__(self, count=1):
        super().__init__()
        self._count = count

    def acquire(self, blocking=True, timeout=-1):
        """Try to spend one permit.

        Returns:
            True when quota remains, False otherwise
        """
        if self._count > 0:
            self._count -= 1
            return True
        return False

    def release(self):
        """Return one permit."""
        self._count += 1
        return True

    def __str__(self):
        return f"CountLock(count={self._count})"
