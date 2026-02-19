"""
event_worker - zoo_framework/workers/event_worker.py

模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""

event_worker - zoo_framework/workers/event_worker.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta

from typing import TYPE_CHECKING

import gevent

from zoo_framework.core.aop import cage
    """EventWorker - 类功能描述

    TODO: 添加类功能详细描述
    """
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.workers import BaseWorker

if TYPE_CHECKING:
    from zoo_framework.event import EventChannel
    from zoo_framework.fifo.node import EventNode


@cage
class EventWorker(BaseWorker):
    """EventWorker - 类功能描述"""
    def __init__(self):
        BaseWorker.__init__(self, {"is_loop": True, "delay_time": 5, "name": "EventWorker"})
        self.is_loop = True

        # 事件处理器注册器
        self.eventChannelManager: EventChannelManager = EventChannelManager()

    def _execute(self):
        from zoo_framework.params import EventParams

        channel_names = self.eventChannelManager.get_all_channel_name()
        g_queue = []
        # TODO:获得除去失败事件通道的所有事件通道
        for channel_name in channel_names:
            channel: EventChannel = self.eventChannelManager.get_channel(channel_name)
            if channel is None:
                continue
            # 获得所有的事件通道
            while channel.size() > 0:
                event_node: EventNode = channel.pop_value()
                # 判断事件是否过期
                if event_node.is_expire():
                    event_node.expire_callback()
                    continue
                # 获得事件反应器
                reactors = self.eventChannelManager.get_channel_reactors(event_node)
                # 如果这里为空，需要查看node 是否有重试次数，如果有重试次数，需要重新放入队列
                if len(reactors) == 0:
                    if event_node.get_retry_times() > 0:
                        event_node.retry_times = event_node.get_retry_times() - 1
                        channel.push_event(event_node)
                    continue
                for reactor in reactors:
                    # 执行事件反应器
                    g = gevent.spawn(reactor.perform, (event_node.content, event_node.topic))
                    g_queue.append(g)

        # 根据优先级排序

        if len(g_queue) > 0:
            # 执行处理方法
            gevent.joinall(g_queue, timeout=EventParams.EVENT_JOIN_TIMEOUT)
