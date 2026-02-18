"""params - zoo_framework/core/aop/params.py

模块功能描述：

作者: XiangMeng
版本: 0.5.1-beta

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
            param_value = params_path.get_value()
            default_value = params_path.get_default()
            value = ParamsFactory().get_params(param_value, default_value=default_value)
            setattr(cls, param, value)
        config_params[cls.__name__] = cls
        return cls

    return inner()
