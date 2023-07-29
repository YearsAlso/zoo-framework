import time

import gevent

from zoo_framework.reactor import BaseReactor
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
        self.eventReactorRegister = EventReactorManager()
        # 注册默认事件处理器
        self.eventReactorRegister.register("default", BaseReactor())

    def _execute(self):

        from zoo_framework.params import EventParams
        while True:
            g_queue = []
            # 获得需要处理的事件
            while EventFIFO.size() > 0:
                node: EventFIFONode = EventFIFO.pop_value()
                if node is None:
                    continue
                handler = self.eventReactorRegister.get_reactor(node.provider_name)
                g = gevent.spawn(handler.execute, (node.topic, node.content, node.provider_name))
                g_queue.append(g)

            if len(g_queue) > 0:
                # 执行处理方法
                gevent.joinall(g_queue, timeout=EventParams.EVENT_JOIN_TIMEOUT)

            time.sleep(EventParams.EVENT_SLEEP_TIME)
