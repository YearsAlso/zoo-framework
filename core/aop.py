from core import ParamsFactory, ParamPath


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


def params():
    def inner(cls):
        params_list = dir(cls)
        for param in params_list:
            param_path = getattr(cls, param)
            if not isinstance(param_path,ParamPath):
                continue
            value = ParamsFactory().get_params(param_path)
            setattr(cls, param, value)

    return inner
