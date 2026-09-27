from .base_lock import BaseLock


class CountLock(BaseLock):
    """按剩余次数放行的计数闸门.

    容量为 N 时前 N 次 ``acquire`` 成功、第 N+1 次失败；每次 ``release``
    归还一次额度。

    注意：本类覆写了 ``acquire`` / ``release``，因此**不提供互斥、也不线程
    安全**（``self._count`` 的读改写不是原子操作），实际并未使用 ``BaseLock``
    持有的那把锁。它仅适用于单线程内的次数控制。
    """

    def __init__(self, count=1):
        super().__init__()
        self._count = count

    def acquire(self, blocking=True, timeout=-1):
        """尝试放行一次.

        Returns:
            还有剩余额度时为 True，否则为 False
        """
        if self._count > 0:
            self._count -= 1
            return True
        return False

    def release(self):
        """归还一次额度."""
        self._count += 1
        return True

    def __str__(self):
        return f"CountLock(count={self._count})"
