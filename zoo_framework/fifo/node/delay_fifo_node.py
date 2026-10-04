import time


class DelayFIFONode:
    """延迟FIFO节点."""

    def __init__(self, value, index, expired_time, loop_times=1):
        self.value = value
        self.expired_time = expired_time
        self.loop_times = loop_times
        self.index = index

    def is_expire(self):
        """是否已过期.

        ``expired_time`` MUST 是**单调时钟**时刻（``time.monotonic()`` 基准）。
        用墙钟判定会让 NTP 校时或夏令时跳变把未到期的节点判成到期（或反之）。
        """
        if self.expired_time <= time.monotonic():
            return True
        return None
