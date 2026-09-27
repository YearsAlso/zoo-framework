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
        """将事件推入事件队列.

        注意：`provider_name` 必须写到事件的 `channel_name` 上——它决定事件
        归属哪个通道队列，丢弃它会让所有事件都落到默认通道，通道隔离随之失效。
        """
        node = EventNode(topic=topic, content=content, channel_name=provider_name)
        super().push_value(node)

    def get_top(self):
        """获取事件队列的第一个事件."""
        if self.size() > 0:
            return self._fifo[0]
        return None

    def has_event(self, event):
        """判断事件是否存在.

        必须用包含性判断：`list.index()` 在未命中时抛 `ValueError` 而不是返回 -1，
        而本方法的调用方（`EventChannel.refresh_event`、`EventProvider.refresh`）
        的正常路径恰恰是"未命中则不做处理"。
        """
        return event in self._fifo

    def replace(self, event):
        """替换事件；事件不存在时不做处理."""
        if event not in self._fifo:
            return
        self._fifo[self._fifo.index(event)] = event
