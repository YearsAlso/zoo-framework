from .base_fifo import BaseFIFO


class SingleFIFO(BaseFIFO):
    """单一值队列."""

    index_list = {}

    def __init__(self):
        BaseFIFO.__init__(self)
        self.pop_pointer = 0

    def push_value(self, value):
        index = self._fifo.index(value)
        if index == -1:
            self._fifo.push(value)
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
