from zoo_framework.handler.event_reactor import EventReactor
from .params_factory import ParamsFactory
from .params_path import ParamsPath

cage_list = []


def cage(cls):
    def _cage():
        if cls not in cage_list:
            cage_list[cls] = cls()
        return cage_list[cls]
    
    return _cage


worker_threads = []


def worker():
    def inner(cls):
        worker_threads.append(cls())
        return cls
    
    return inner


event_map = {}


def event(topic: str, handler_name="default"):
    def inner(func):
        event_map[topic] = func
        return func
    
    return inner


config_params = {}


def params(cls):
    def inner():
        if config_params.get(cls.__name__) is not None:
            return config_params[cls.__name__]
        params_list = dir(cls)
        for param in params_list:
            params_path = getattr(cls, param)
            if not isinstance(params_path, ParamsPath):
                continue
            param_value = params_path.get_value()
            default_value = params_path.get_default()
            value = ParamsFactory().get_params(param_value, default_value=default_value)
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
