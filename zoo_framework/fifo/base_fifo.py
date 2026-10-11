"""FIFO base class: each instance holds its own queue storage.

Historical note: `_fifo` used to be a **class attribute** with all methods
being classmethods, so every instance shared one list - two different
`EventFIFO` instances saw each other's enqueued events, making channel
isolation effectively void. Now instance-level storage.

The generic parameter `_T` is a **pure annotation**: a bare `BaseFIFO` still
equals `BaseFIFO[Any]`, existing usage unaffected; while the subclasses bind
their own element types (`EventFIFO[EventNode]` / `DelayFIFO[DelayFIFONode]`
/ `SingleFIFO[Any]`) - otherwise the head read and `popleft()` in the base
class could only be inferred as `Any`, and returning it from a function that
declares a concrete return type trips `no-any-return` (narrowing `_fifo` to
`list[EventNode]` used to be wrong: `DelayFIFO` stores `DelayFIFONode`,
which is not a subclass of `EventNode`).

Storage choice (align-execution-primitives): historically `list` +
`pop(0)`, an O(n) dequeue, measured 12.4x slower than
`collections.deque` at 10k queued items; after switching to `deque` the API
and the semantics are unchanged, including **an empty queue's
`pop_value()` returning None** (the event consume path relies on this
returns-None semantics to bridge the concurrent gap between `size()` and
the pop, MUST NOT be changed to raise `IndexError`).
"""

from collections import deque
from typing import Generic, TypeVar

# PEP 695 泛型（`class BaseFIFO[_T]:`）需要 Python 3.12+，而本项目的下界是 3.11，
# 因此 `Generic` 形式是唯一合法写法，UP046 不适用、无需抑制
# （同见 utils/thread_safe_dict.py 的说明）。
_T = TypeVar("_T")


class BaseFIFO(Generic[_T]):
    """FIFO base class."""

    def __init__(self):
        self._fifo: deque[_T] = deque()

    def push_value(self, value: _T) -> None:
        """Enqueue."""
        self._fifo.append(value)

    def pop_value(self) -> _T | None:
        """Dequeue; returns None when the queue is empty."""
        if len(self._fifo) <= 0:
            return None

        return self._fifo.popleft()

    def push_values(self, values: list[_T]) -> None:
        """Enqueue in batch."""
        self._fifo.extend(values)

    def size(self) -> int:
        """The current queue length."""
        return len(self._fifo)

    def push_values_if_null(self, value: _T) -> None:
        """Enqueue only when the value is not already in the queue."""
        if value not in self._fifo:
            self._fifo.append(value)
