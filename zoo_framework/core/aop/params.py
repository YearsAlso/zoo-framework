from ..params_factory import ParamsFactory
from ..params_path import ParamsPath

# 解析缓存：进程级共享，须由测试单独清空（见 tests/test_config_resolution.py 的 fixture）。
# 【已知欠债】属容器外、未收编的载体；依据与判据见 specs/scoped-container 的
# 「框架自身的进程级共享 MUST 被显式归类」。
config_params: dict = {}

# 每个参数类解析时所处的配置载入世代（变更 aop-determinism / #51）。
# 解析发生在导入期，无法在导入现场知道"稍后会有配置被读到"；把当时的世代
# 记下来，Master 构造读到配置后即可核对哪些类被冻结在默认值。
_resolved_generation: dict[str, int] = {}


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
        # 记录解析世代（#51）：供 Master 构造时核对"冻结在默认值"的类
        _resolved_generation[key] = ParamsFactory.generation()
        config_params[key] = cls
        return cls

    return inner()


def stale_param_classes() -> list[str]:
    """列出"在从未读到配置的世代里解析过"的参数类（#51）.

    判据是 `gen == 0`（解析时配置文件不存在/未被读到）而不是 `gen < 当前世代`：
    后者会把"首次查询时顺带读到配置、取值本来就正确"的类也误判——那正是框架大
    多数值的正常工作形态。调用方（`Master.__init__`）仅在成功读到非零世代配置时
    才核对，因此"全程无配置文件"的合法运行不触发。
    """
    return [key for key, gen in _resolved_generation.items() if gen == 0]


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
