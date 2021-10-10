from zoo_framework import cage
from zoo_framework.handler import BaseHandler


@cage
class EventReactor:
    handler_map: {str: BaseHandler} = {
        "default": BaseHandler()
    }
    
    def dispatch(self, topic, content, handler_name="default"):
        handler = self.handler_map[handler_name]
        handler.handle(topic, content)
    
    def register(self, handler_name: str, handler: BaseHandler):
        self.handler_map[handler_name] = handler
