import time


class DelayFIFONode:
    """A delayed FIFO node."""

    def __init__(self, value, index, expired_time, loop_times=1):
        self.value = value
        self.expired_time = expired_time
        self.loop_times = loop_times
        self.index = index

    def is_expire(self):
        """Whether expired.

        ``expired_time`` MUST be a **monotonic-clock** instant (based on
        ``time.monotonic()``). Judging by wall clock would let NTP
        corrections or DST jumps misjudge not-yet-expired nodes as expired
        (or vice versa).
        """
        if self.expired_time <= time.monotonic():
            return True
        return None
