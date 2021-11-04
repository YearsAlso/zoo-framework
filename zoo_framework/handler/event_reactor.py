from zoo_framework import cage
from zoo_framework.handler import BaseHandler


@cage
class EventReactor:
    handler_map: {str: BaseHandler} = {
        "default": BaseHandler()
    }

    @classmethod
    def dispatch(cls, topic, content, handler_name="default"):
        handler = cls.handler_map[handler_name]
        handler.handle(topic, content)
    
    @classmethod
    def register(cls, handler_name: str, handler: BaseHandler):
        EventReactor.handler_map[handler_name] = handler
