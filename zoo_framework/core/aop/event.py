event_map = {}


def event(topic: str, handler: str = "default"):
    def inner(func):
        if event_map.get(handler) is None:
            event_map[handler] = {}
        event_map[handler][topic] = func
        return func
    
    return inner
