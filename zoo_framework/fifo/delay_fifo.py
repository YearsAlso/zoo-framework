from collections import deque

from .base_fifo import BaseFIFO
from .node import DelayFIFONode


class DelayFIFO(BaseFIFO[DelayFIFONode]):
    """The delayed queue."""

    def __init__(self):
        super().__init__()
        # Same-shaped storage as the base class (align-execution-primitives:
        # deque, O(1) dequeue); this class historically reset it to a list
        # here, and the two sources of truth MUST be replaced in sync.
        self._fifo = deque()

    def push_value(self, value: DelayFIFONode):
        self._fifo.append(value)

    def pop_value(self):
        if len(self._fifo) <= 0:
            return None

        return self._fifo.popleft()

    def is_exist(self, value):
        return value in self._fifo

    def size(self):
        return len(self._fifo)

    def get_expire_values(self):
        """Get the expired values.

        The original signature carried ``current_time`` while the body called
        ``node.is_expire(current_time)`` - yet
        ``DelayFIFONode.is_expire()`` **takes no argument**: by design the
        node reads its own monotonic clock (its docstring notes that wall
        clock would be misled by NTP corrections or DST jumps), and that
        signature is directly exercised by multiple tests in
        tests/test_execution_time.py. So the old call raised TypeError at
        runtime. The method had no callers, which is why it never
        surfaced; the mismatch only became visible to type checking after
        `_fifo` was parameterized as `list[DelayFIFONode]`.
        """
        values = []
        for node in self._fifo:
            if node.is_expire():
                values.append(node)
        return values
