event_map = {}


def event(topic: str, handler_name: str = "default"):
    def _event(func):
        if event_map.get(handler_name) is None:
            event_map[handler_name] = {}
        event_map[handler_name][topic] = func
        return func

    return _event
