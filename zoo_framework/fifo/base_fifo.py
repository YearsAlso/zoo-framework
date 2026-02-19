"""base_fifo - zoo_framework/fifo/base_fifo.py

基础FIFO（先进先出）队列模块.

功能:
- 基本的队列操作（入队、出队）
- 队列状态监控
- 容量管理
- 线程安全操作

作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.fifo.node import EventNode


class BaseFIFO:
    """基础FIFO队列类

    提供基本的先进先出队列功能.
    """

    _fifo = []

    def __init__(self, max_size=1000):
        self._fifo = []
        self._max_size = max_size

    def push(self, event_node: EventNode):
        """将事件节点推入队列"""
        if len(self._fifo) < self._max_size:
            self._fifo.append(event_node)
            return True
        return False

    def pop(self):
        """从队列中弹出事件节点"""
        if self._fifo:
            return self._fifo.pop(0)
        return None

    def size(self):
        """获取队列大小"""
        return len(self._fifo)

    def is_empty(self):
        """检查队列是否为空"""
        return len(self._fifo) == 0

    def is_full(self):
        """检查队列是否已满"""
        return len(self._fifo) >= self._max_size

    def clear(self):
        """清空队列"""
        self._fifo.clear()

    def peek(self):
        """查看队列头部元素（不移除）"""
        if self._fifo:
            return self._fifo[0]
        return None
