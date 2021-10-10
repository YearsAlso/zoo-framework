from zoo_framework import BaseFIFO
from zoo_framework.handler import BaseHandler


class EventFIFO(BaseFIFO):
    
    def __init__(self, handler: BaseHandler):
        BaseFIFO.__init__(self)
        self.handler = handler
    
    def push_value(self, value: dict):
        topic = value.get("topic")
        content = value.get("content")
        self.fifo.append(topic, content)
