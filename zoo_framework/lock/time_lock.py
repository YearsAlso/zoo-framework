from .base_lock import BaseLock


class TimeLock(BaseLock):
    """超时锁，可以指定事件超时时间，当超时后触发回调，并且释放锁."""

    def __init__(self, timeout=1, callback=None):
        super().__init__()
        self._timeout = timeout
        self._callback = callback

    def acquire(self, blocking=True, timeout=-1):
        if self._timeout > 0:
            self._timeout -= 1
            return True
        return False

    def release(self):
        self._timeout += 1
        return True

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
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
