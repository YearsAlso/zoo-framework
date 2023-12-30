from .base_lock import BaseLock


class CountLock(BaseLock):
    """
    次数锁，可以指定次数，每次acquire后次数减1，次数为0时无法acquire
    """

    def __init__(self, count=1):
        super().__init__()
        self._count = count

    def acquire(self, blocking=True, timeout=-1):
        if self._count > 0:
            self._count -= 1
            return True
        else:
            return False

    def release(self):
        self._count += 1
        return True

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return True

    def __str__(self):
        return f"CountLock(count={self._count})"
