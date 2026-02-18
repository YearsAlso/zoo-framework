"""delay_fifo_node - zoo_framework/fifo/node/delay_fifo_node.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta

import time


class DelayFIFONode:
    """延迟FIFO节点."""

    def __init__(self, value, index, expired_time, loop_times=1):
        self.value = value
        self.expired_time = expired_time
        self.loop_times = loop_times
        self.index = index

    def is_expire(self):
        if self.expired_time <= time.time():
            return True
        return None
"""
