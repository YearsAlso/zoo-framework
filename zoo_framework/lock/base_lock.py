"""Base class of lock primitives.

Design note: this uses **composition** rather than inheritance - a hard
constraint under Python 3.13, not a style preference. None of the three
candidate base classes can be subclassed (all verified by experiment):

- ``threading.Lock``: a class, but the underlying ``_thread.lock`` is not a
  legal base type
  (``TypeError: type '_thread.lock' is not an acceptable base type``)
- ``threading.RLock``: a factory function, not a class
- ``multiprocessing.Lock``: a bound method, not a class

Hence ``BaseLock`` holds a real lock and delegates ``acquire`` /
``release``.
"""

import threading


class BaseLock:
    """Base class of lock primitives: holds a reentrant lock and delegates acquire and release.

    Defaults to ``threading.RLock``, consistent with the rest of the
    framework (``master.py``, ``state_machine_work.py``,
    ``persistence_scheduler.py``).

    A subclass that overrides ``acquire`` / ``release`` no longer uses this
    lock and therefore no longer provides mutual exclusion - the overrider
    must document it.
    """

    def __init__(self):
        self._lock = threading.RLock()

    def acquire(self, blocking=True, timeout=-1):
        """Acquire the lock.

        Args:
            blocking: whether to block waiting
            timeout: the blocking-wait timeout in seconds; below 0 means no
                timeout

        Returns:
            Whether the acquire succeeded
        """
        if timeout is None or timeout < 0:
            return self._lock.acquire(blocking)
        return self._lock.acquire(blocking, timeout)

    def release(self):
        """Release the lock.

        Returns:
            Always True, keeping the existing caller contract
        """
        self._lock.release()
        return True

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Do not return a truthy value: returning True swallows exceptions
        # raised inside the body. A bare return falls to None, letting
        # exceptions propagate as usual.
        self.release()
        return

    def __str__(self):
        return f"{self.__class__.__name__}()"
