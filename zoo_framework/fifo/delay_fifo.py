"""delay_fifo - zoo_framework/fifo/delay_fifo.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta
"""

from .base_fifo import BaseFIFO
from .node import DelayFIFONode


class DelayFIFO(BaseFIFO):
    """延迟队列."""

    def __init__(self):
        super().__init__()
        self._fifo = []

    def push_value(self, value: DelayFIFONode):
        self._fifo.append(value)

    def pop_value(self):
        if len(self._fifo) <= 0:
            return None

        return self._fifo.pop(0)

    def is_exist(self, value):
        return value in self._fifo

    def size(self):
        return len(self._fifo)

    def get_expire_values(self, current_time):
        """获取过期的值
        :param current_time:
        :return:
        """
        values = []
        for node in self._fifo:
            if node.is_expire(current_time):
                values.append(node)
        return values
