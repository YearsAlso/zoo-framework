from collections import deque

from .base_fifo import BaseFIFO
from .node import DelayFIFONode


class DelayFIFO(BaseFIFO[DelayFIFONode]):
    """延迟队列."""

    def __init__(self):
        super().__init__()
        # 与基类同型存储（align-execution-primitives：deque，出队 O(1)）；
        # 本类历史上在这里重置为 list，两处真源 MUST 同步替换。
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
        """获取过期的值.

        原签名带 ``current_time``，方法体却以 ``node.is_expire(current_time)`` 调用 —— 而
        ``DelayFIFONode.is_expire()`` **不收参数**：它设计上由节点自己读单调时钟（其 docstring
        写明用墙钟会被 NTP 校时或夏令时跳变误判），且该签名被 tests/test_execution_time.py
        多处直接覆盖。故此调用会在运行期抛 TypeError。本方法此前无调用者，所以一直没暴露；
        类型检查在 `_fifo` 被参数化为 `list[DelayFIFONode]` 之后才看得见这个不匹配。
        """
        values = []
        for node in self._fifo:
            if node.is_expire():
                values.append(node)
        return values
