import time

import gevent

from zoo_framework.event import EventChannel
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.reactor import EventReactor
from zoo_framework.core.aop import cage
from zoo_framework.fifo.event_fifo import EventFIFO
from zoo_framework.fifo.node import EventFIFONode
from zoo_framework.workers import BaseWorker
from zoo_framework.reactor import EventReactorManager


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
        # 注册默认事件处理器
        self.eventChannelManager.register_reactor("default")

        self.eventReactorManager: EventReactorManager = EventReactorManager()

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
                if event_node is None:
                    continue
                reactor = channel.get_reactor(event_node.reactor_name)
                g = gevent.spawn(reactor.execute, (event_node.topic, event_node.content, event_node.reactor_name))

                g_queue.append(g)

        # 根据优先级排序

        if len(g_queue) > 0:
            # 执行处理方法
            gevent.joinall(g_queue, timeout=EventParams.EVENT_JOIN_TIMEOUT)
