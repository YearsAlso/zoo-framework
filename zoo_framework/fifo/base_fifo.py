"""FIFO 基类：每个实例持有独立的队列存储.

历史说明：`_fifo` 曾是**类属性**、且所有方法都是类方法，导致全部实例共享同一个
列表——两个不同的 `EventFIFO` 实例会互相看到对方入队的事件，事件通道隔离因此
形同虚设。此处改为实例级存储。

泛型参数 `_T` 是**纯注解**：裸写 `BaseFIFO` 仍等价于 `BaseFIFO[Any]`，既有用法不受影响；
而各子类绑定自己的元素类型（`EventFIFO[EventNode]` / `DelayFIFO[DelayFIFONode]` /
`SingleFIFO[Any]`）——否则基类里队首读取与 `popleft()` 只能推成 `Any`，凡从声明了
具体返回类型的函数里返回它就报 `no-any-return`（原先把 `_fifo` 收窄成 `list[EventNode]`
是错的：`DelayFIFO` 存的是 `DelayFIFONode`，并非 `EventNode` 的子类）。

存储选型（align-execution-primitives）：历史上用 `list` + `pop(0)`，出队为 O(n)，
队列 10k 时实测比 `collections.deque` 慢 12.4x；改用 `deque` 后 API 与语义不变，
包括**空队 `pop_value()` 返回 None**（事件消费路径在 `size()` 与取出之间的并发空档
依赖这个返 None 语义兜底，MUST NOT 改成抛 `IndexError`）。
"""

from collections import deque
from typing import Generic, TypeVar

# ruff 的 UP046 要求改用 PEP 695 的 `class BaseFIFO[_T]:`，而 mypy 1.7.1 不支持 PEP 695
# （详见 utils/thread_safe_dict.py 的同类说明）。两工具要求相反，故保留 Generic 写法 + 定向 noqa。
_T = TypeVar("_T")


class BaseFIFO(Generic[_T]):  # noqa: UP046
    """FIFO 基类."""

    def __init__(self):
        self._fifo: deque[_T] = deque()

    def push_value(self, value: _T) -> None:
        """入队."""
        self._fifo.append(value)

    def pop_value(self) -> _T | None:
        """出队；队列为空时返回 None."""
        if len(self._fifo) <= 0:
            return None

        return self._fifo.popleft()

    def push_values(self, values: list[_T]) -> None:
        """批量入队."""
        self._fifo.extend(values)

    def size(self) -> int:
        """当前队列长度."""
        return len(self._fifo)

    def push_values_if_null(self, value: _T) -> None:
        """仅当队列中不存在该值时才入队."""
        if value not in self._fifo:
            self._fifo.append(value)
