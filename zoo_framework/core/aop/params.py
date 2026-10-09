from ..params_factory import ParamsFactory
from ..params_path import ParamsPath

# Resolution cache: process-level shared state, to be cleared separately by
# tests (see the fixture in tests/test_config_resolution.py).
# [Known debt] a carrier outside the container, not yet absorbed; rationale
# and criteria in specs/scoped-container's "process-level sharing created by
# the framework itself MUST be explicitly classified".
config_params: dict = {}

# The config-loading generation each parameter class was resolved in
# (aop-determinism / #51).
# Resolution happens at import time, where "a config will be read later"
# cannot be known on the spot; recording the generation at that moment lets
# Master, after reading the config, check which classes were frozen at
# defaults.
_resolved_generation: dict[str, int] = {}


def _cache_key(cls) -> str:
    """The resolution-cache key: the qualified name (module + qualname).

    MUST NOT be the bare class name alone - two same-named parameter classes
    defined in different places would hit the same record, and the later
    definition would **skip resolution** and silently reuse the former's
    config values, all at import time with no hint.
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
    """List parameter classes resolved in a generation that never read a config (#51).

    The criterion is `gen == 0` (no config file existed / was read at
    resolution time), not `gen < the current generation`: the latter would
    also misjudge classes that "read the config incidentally on the first
    query, whose values were already correct" - that is exactly the normal
    working shape for most framework values. The caller (`Master.__init__`)
    checks only after successfully reading a nonzero-generation config, so a
    legitimate "no config file at any point" run does not trigger it.
    """
    return [key for key, gen in _resolved_generation.items() if gen == 0]


def _resolve(params_path: ParamsPath):
    """Resolve a config item in the order primary path -> aliases -> default."""
    value = ParamsFactory().get_params(params_path.get_value(), default_value=None)
    if value is not None:
        return value

    for alias in params_path.get_aliases():
        value = ParamsFactory().get_params(alias, default_value=None)
        if value is not None:
            return value

    return params_path.get_default()
