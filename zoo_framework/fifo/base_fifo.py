"""
base_fifo - zoo_framework/fifo/base_fifo.py

模块功能描述：
    """BaseFIFO - 类功能描述

    TODO: 添加类功能详细描述
    """
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.fifo.node import EventNode


class BaseFIFO:
    _fifo = []

    def __init__(self):
        pass

    @classmethod
    def push_value(cls, value):
        cls._fifo.append(value)

    @classmethod
    def pop_value(cls) -> EventNode or None:
        if len(cls._fifo) <= 0:
            return None

        return cls._fifo.pop(0)

    @classmethod
    def push_values(cls, values: list):
        cls._fifo.extend(values)

    @classmethod
    def size(cls):
        return len(cls._fifo)

    @classmethod
    def push_values_if_null(cls, value: EventNode):
        if cls._fifo.index(value) == -1:
            cls._fifo.append(value)
