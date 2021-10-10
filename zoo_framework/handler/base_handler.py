from zoo_framework.core import event_map


class BaseHandler:
    
    def __init__(self):
        pass
    
    def _on_error(self, topic, content, exception: Exception):
        pass
    
    def handle(self, topic, content):
        event_handler = event_map.get(topic)
        if event_handler is None:
            pass
        
        try:
            event_handler(content)
        except Exception as e:
            self._on_error(topic, content, e)
