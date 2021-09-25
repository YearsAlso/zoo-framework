from .params_factory import ParamsFactory
from .param_path import ParamPath


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

def params(cls):
    def inner():
        if config_params.get(cls.__name__) is not None:
            return config_params[cls.__name__]
        params_list = dir(cls)
        for param in params_list:
            param_path = getattr(cls, param)
            if not isinstance(param_path,ParamPath):
                continue
            value = ParamsFactory().get_params(param_path)
            setattr(cls, param, value)
        config_params[cls.__name__] = cls
        return cls
    return inner()


config_funcs = {}

def configure(topic: str):
    def inner(func):
        config_funcs[topic] = func
        return func

    return inner