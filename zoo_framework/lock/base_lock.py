"""锁原语的基类.

设计说明：这里使用**组合**而非继承，这是 Python 3.13 下的硬约束而非风格偏好。
以下三种候选基类都无法被子类化（均实测确认）：

- ``threading.Lock``：虽是类，但底层 ``_thread.lock`` 不是合法基类型
  （``TypeError: type '_thread.lock' is not an acceptable base type``）
- ``threading.RLock``：是工厂函数，不是类
- ``multiprocessing.Lock``：是绑定方法，不是类

因此 ``BaseLock`` 持有一把真实锁并委托 ``acquire`` / ``release``。
"""

import threading


class BaseLock:
    """锁原语基类：持有一把可重入锁并委托获取与释放.

    默认使用 ``threading.RLock``，与框架其余部分（``master.py``、
    ``state_machine_work.py``、``persistence_scheduler.py``）保持一致。

    子类若覆写 ``acquire`` / ``release``，即不再使用这把锁，也就不再提供
    互斥语义——覆写者需自行在文档中说明。
    """

    def __init__(self):
        self._lock = threading.RLock()

    def acquire(self, blocking=True, timeout=-1):
        """获取锁.

        Args:
            blocking: 是否阻塞等待
            timeout: 阻塞等待的超时秒数，小于 0 表示不设超时

        Returns:
            是否成功获取
        """
        if timeout is None or timeout < 0:
            return self._lock.acquire(blocking)
        return self._lock.acquire(blocking, timeout)

    def release(self):
        """释放锁.

        Returns:
            固定为 True，保持既有调用方契约
        """
        self._lock.release()
        return True

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 不要返回真值：返回 True 会吞掉上下文体内抛出的异常。
        # 此处用裸 return 落到 None，异常正常向外传播。
        self.release()
        return

    def __str__(self):
        return f"{self.__class__.__name__}()"
