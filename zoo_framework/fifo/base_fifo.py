"""FIFO 基类：每个实例持有独立的队列存储.

历史说明：`_fifo` 曾是**类属性**、且所有方法都是类方法，导致全部实例共享同一个
列表——两个不同的 `EventFIFO` 实例会互相看到对方入队的事件，事件通道隔离因此
形同虚设。此处改为实例级存储。
"""

from zoo_framework.fifo.node import EventNode


class BaseFIFO:
    """FIFO 基类."""

    def __init__(self):
        self._fifo: list = []

    def push_value(self, value):
        """入队."""
        self._fifo.append(value)

    def pop_value(self) -> EventNode | None:
        """出队；队列为空时返回 None."""
        if len(self._fifo) <= 0:
            return None

        return self._fifo.pop(0)

    def push_values(self, values: list):
        """批量入队."""
        self._fifo.extend(values)

    def size(self):
        """当前队列长度."""
        return len(self._fifo)

    def push_values_if_null(self, value: EventNode):
        """仅当队列中不存在该值时才入队."""
        if value not in self._fifo:
            self._fifo.append(value)
