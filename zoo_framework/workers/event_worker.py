import time

import gevent

from zoo_framework.handler import BaseHandler
from zoo_framework.core.aop import cage
from zoo_framework.fifo.event_fifo import EventFIFO
from zoo_framework.fifo.node import EventFIFONode
from zoo_framework.workers import BaseWorker
from zoo_framework.handler import HandlerRegister


@cage
class EventWorker(BaseWorker):
    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 5,
            "name": "EventWorker"
        })
        self.is_loop = True

        self.eventReactor = HandlerRegister()
        self.eventReactor.register("default", BaseHandler())

    def _execute(self):

        from zoo_framework.params import EventParams
        while True:
            g_queue = []
            # 获得需要处理的事件
            while EventFIFO.size() > 0:
                node: EventFIFONode = EventFIFO.pop_value()
                if node is None:
                    continue
                handler = self.eventReactor.get_handler(node.handler_name)
                g = gevent.spawn(handler.handle, (node.topic, node.content, node.handler_name))
                g_queue.append(g)

            # 执行处理方法
            gevent.joinall(g_queue, timeout=EventParams.EVENT_JOIN_TIMEOUT)
            time.sleep(0.2)
