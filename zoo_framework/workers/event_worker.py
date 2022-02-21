import time

import gevent

from zoo_framework.fifo.event_fifo import EventFIFO
from zoo_framework.fifo.node import EventFIFONode
from zoo_framework.workers import BaseWorker
from zoo_framework.handler.event_reactor import EventReactor


class EventWorker(BaseWorker):
    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 5,
            "name": "EventWorker"
        })
        self.is_loop = True
        
        self.eventReactor = EventReactor()
    
    def _execute(self):
        while True:
            # 获得需要处理的事件
            while EventFIFO.size() > 0:
                node: EventFIFONode = EventFIFO.pop_value()
                if node is None:
                    continue
                handler = self.eventReactor.get_handler(node.handler_name)
                g = gevent.spawn(handler.handle, (node.topic, node.content, node.handler_name))
                # 执行处理方法
                g.start()
            time.sleep(0.2)
