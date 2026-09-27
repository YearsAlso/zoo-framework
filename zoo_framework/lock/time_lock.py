from .base_lock import BaseLock


class TimeLock(BaseLock):
    """按剩余次数放行的计数闸门（与 CountLock 语义相同）.

    历史说明：本类旧文档声称具备超时与回调语义，但实现中从未提供超时计时或
    回调调用——``__init__`` 接收的 ``callback`` 只被保存、从未被调用，
    ``timeout`` 实际被当作剩余放行次数递减。此处按实际行为如实描述，避免
    文档与实现不符。

    注意：与 ``CountLock`` 一样，本类覆写了 ``acquire`` / ``release``，因此
    **不提供互斥、也不线程安全**，实际并未使用 ``BaseLock`` 持有的那把锁。
    它仅适用于单线程内的次数控制。
    """

    def __init__(self, timeout=1, callback=None):
        """初始化计数闸门.

        Args:
            timeout: 剩余放行次数（参数名沿用历史，语义实为次数）
            callback: 历史遗留参数，当前实现不会调用它
        """
        super().__init__()
        self._timeout = timeout
        self._callback = callback

    def acquire(self, blocking=True, timeout=-1):
        """尝试放行一次.

        Returns:
            还有剩余额度时为 True，否则为 False
        """
        if self._timeout > 0:
            self._timeout -= 1
            return True
        return False

    def release(self):
        """归还一次额度."""
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
