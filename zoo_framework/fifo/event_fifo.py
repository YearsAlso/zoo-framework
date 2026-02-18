"""
event_fifo - zoo_framework/fifo/event_fifo.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.utils import LogUtils

from .base_fifo import BaseFIFO
from .node import EventNode


class EventFIFO(BaseFIFO):
    """事件队列."""

    def push_value(self, value):
        """将事件推入事件队列."""
        try:
            if isinstance(value, dict):
                node = EventNode(**value)
            elif isinstance(value, EventNode):
                node = value
            else:
                # 对于非 dict 和非 EventNode 的值，创建一个默认事件节点
                node = EventNode(topic="default", content=str(value))
            super().push_value(node)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    def dispatch(self, topic, content, provider_name="default"):
        """将事件推入事件队列."""
        node = EventNode(topic=topic, content=content)
        super().push_value(node)

    def get_top(self):
        """获取事件队列的第一个事件."""
        if self.size() > 0:
            return self._fifo[0]
        return None

    def has_event(self, event):
        """判断事件是否存在."""
        return self._fifo.index(event) != -1

    def replace(self, event):
        """替换事件."""
        index = self._fifo.index(event)
        if index != -1:
            self._fifo[index] = event
