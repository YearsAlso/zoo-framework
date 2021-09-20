def singleton(cls):
    _instance = {}

    def _singleton():
        if cls not in _instance:
            _instance[cls] = cls()
        return _instance[cls]

    return _singleton


worker_threads = []


def worker():
    def inner(cls):
        worker_threads.append(cls())
        return cls
    
    return inner


websocket_events = {}


def event(topic: str):
    def inner(func):
        websocket_events[topic] = func
        return func
    
    return inner
