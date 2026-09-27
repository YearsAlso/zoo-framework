from ..params_factory import ParamsFactory
from ..params_path import ParamsPath

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
            value = _resolve(params_path)
            setattr(cls, param, value)
        config_params[cls.__name__] = cls
        return cls

    return inner()


def _resolve(params_path: ParamsPath):
    """按首选路径 → 别名 → 默认值的顺序解析配置项。"""
    value = ParamsFactory().get_params(params_path.get_value(), default_value=None)
    if value is not None:
        return value

    for alias in params_path.get_aliases():
        value = ParamsFactory().get_params(alias, default_value=None)
        if value is not None:
            return value

    return params_path.get_default()
