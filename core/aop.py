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


config_params = {}


def params(path: str):
    def inner(func):
        if path is None or path == "":
            return
        path_split = path.split(":")
        value = config_params
        for item in path_split:
            if value[item] is None:
                return value
            value = value[item]

    return inner
