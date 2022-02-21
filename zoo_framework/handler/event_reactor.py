from zoo_framework.core.aop import cage
from zoo_framework.handler import BaseHandler


@cage
class EventReactor:
    handler_map: {str: BaseHandler} = {
        "default": BaseHandler()
    }
    
    def __init__(self):
        for key, value in self.handler_map.items():
            from zoo_framework.params import EventParams
            value.set_event_timeout(EventParams.EVENT_JOIN_TIMEOUT)
    
    @classmethod
    def dispatch(cls, topic, content, handler_name="default"):
        handler = cls.get_handler(handler_name)
        handler.handle(topic, content, handler_name)
    
    @classmethod
    def get_handler(cls, handler_name="default"):
        return cls.handler_map.get(handler_name)
    
    @classmethod
    def register(cls, handler_name: str, handler: BaseHandler):
        if not isinstance(handler, BaseHandler):
            raise Exception("Handler is invalid")
        
        cls.handler_map[handler_name] = handler
