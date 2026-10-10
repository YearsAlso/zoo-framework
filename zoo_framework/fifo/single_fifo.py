from typing import Any

from .base_fifo import BaseFIFO


class SingleFIFO(BaseFIFO[Any]):
    """A single-value queue: the same value enqueues once, with its position recorded.

    Note: `index_list` is still a **class attribute** (shared across
    instances); left unchanged here - a known issue.
    """

    index_list: dict = {}

    def __init__(self):
        BaseFIFO.__init__(self)
        self.pop_pointer = 0

    def push_value(self, value):
        """Enqueue (the same value only once); return the value's position.

        Two misuses corrected here:
        - `list.index()` raises `ValueError` on a miss; it cannot serve as a
          "membership check";
        - `list` has no `push` method; appending uses `append`.
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
