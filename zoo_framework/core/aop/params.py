from ..params_factory import ParamsFactory
from ..params_path import ParamsPath

# 解析缓存：进程级共享，须由测试单独清空（见 tests/test_config_resolution.py 的 fixture）。
# 【已知欠债】属容器外、未收编的载体；依据与判据见 specs/scoped-container 的
# 「框架自身的进程级共享 MUST 被显式归类」。
config_params: dict = {}


def _cache_key(cls) -> str:
    """解析缓存的键：限定名（模块 + 限定名）.

    MUST NOT 只用裸类名——两个定义位置不同的同名参数类会命中同一条记录，
    后定义者**跳过解析**、直接复用前者的配置值，且发生在 import 期、无任何提示。
    """
    return f"{cls.__module__}.{cls.__qualname__}"


def params(cls):
    def inner():
        key = _cache_key(cls)
        if config_params.get(key) is not None:
            return config_params[key]
        params_list = dir(cls)
        for param in params_list:
            params_path = getattr(cls, param)
            if not isinstance(params_path, ParamsPath):
                continue
            value = _resolve(params_path)
            setattr(cls, param, value)
        config_params[key] = cls
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
