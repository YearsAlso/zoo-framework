import time

import gevent

from zoo_framework.event import EventChannel
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.reactor import EventReactor
from zoo_framework.core.aop import cage
from zoo_framework.fifo.event_fifo import EventFIFO
from zoo_framework.fifo.node import EventFIFONode
from zoo_framework.workers import BaseWorker


@cage
class EventWorker(BaseWorker):
    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 5,
            "name": "EventWorker"
        })
        self.is_loop = True

        # 事件处理器注册器
        self.eventChannelManager: EventChannelManager = EventChannelManager()

    def _execute(self):
        from zoo_framework.params import EventParams
        channel_names = self.eventChannelManager.get_channel_name_list()
        g_queue = []
        # TODO：获得除去失败事件通道的所有事件通道
        for channel_name in channel_names:
            channel: EventChannel = self.eventChannelManager.get_channel(channel_name)
            if channel is None:
                continue
            # 获得所有的事件通道
            while channel.size() > 0:
                event_node: EventFIFONode = channel.pop_value()
                reactors = self.eventChannelManager.get_perform_reactors(channel_name, event_node.topic)
                for reactor in reactors:
                    # 执行事件反应器
                    g = gevent.spawn(reactor.perform, (event_node.content, event_node.topic))
                    g_queue.append(g)

        # 根据优先级排序

        if len(g_queue) > 0:
            # 执行处理方法
            gevent.joinall(g_queue, timeout=EventParams.EVENT_JOIN_TIMEOUT)
