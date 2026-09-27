from .base_fifo import BaseFIFO


class SingleFIFO(BaseFIFO):
    """单一值队列：同一个值只入队一次，并记录其位置.

    注意：`index_list` 目前仍是**类属性**（跨实例共享），本次未改动，
    属已知问题。
    """

    index_list = {}

    def __init__(self):
        BaseFIFO.__init__(self)
        self.pop_pointer = 0

    def push_value(self, value):
        """入队（同一个值只入队一次），返回该值在队列中的位置.

        修正两处误用：
        - `list.index()` 未命中时抛 `ValueError`，不能当作"包含性检查"；
        - `list` 没有 `push` 方法，追加应为 `append`。
        """
        if value not in self._fifo:
            self._fifo.append(value)
        index = self._fifo.index(value)
        self.index_list[value] = index
        return index

    def pop_value(self):
        if len(self._fifo) <= self.pop_pointer:
            raise Exception("no value to pop")
        value = self._fifo[self.pop_pointer]
        self.pop_pointer += 1
        return value

    def get_value_by_index(self, index):
        return self._fifo[index]

    def get_index(self, value):
        return self.index_list.get(value)
