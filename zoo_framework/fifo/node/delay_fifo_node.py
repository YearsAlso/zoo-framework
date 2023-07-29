import time


class DelayFIFONode(object):
    def __init__(self, value, index, expired_time, loop_times=1):
        self.value = value
        self.expired_time = expired_time
        self.loop_times = loop_times
        self.index = index

    def is_expire(self):
        if self.expired_time <= time.time():
            return True
