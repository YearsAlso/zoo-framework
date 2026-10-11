from typing import TypeVar, cast

# PEP 695 泛型（`def param[T](...)`）需要 Python 3.12+，而本项目的下界是 3.11
# （`requires-python`，`[tool.ruff] target-version = "py311"` 跟随它），因此 `TypeVar`
# 形式是**唯一合法写法**——UP047 不适用，无需抑制。若日后把门槛抬到 3.12+，ruff 会重新
# 要求 PEP 695，而 pre-commit 钉的 mypy 1.7.1 不支持该语法，那时必须先升级 mypy
# （见 docs/contributing/development.md 的「Python 下界的依据」）。
_T = TypeVar("_T")


class ParamsPath:
    """Configuration item path.

    Supports declaring several candidate paths for the same configuration
    item: resolved in the order ``value`` first, then ``aliases`` in turn,
    for compatibility with historical key names. When a candidate is
    missing, the caller decides whether to fall back to the default.

    Args:
        value: the preferred configuration path, like ``worker:pool:size``
        default: the default used when all candidates are missing
        aliases: fallback configuration paths, in order
    """

    def __init__(self, value, default="", aliases=None):
        self.value = value
        self.default = default
        self.aliases = list(aliases or [])

    def get_default(self):
        return self.default

    def get_value(self):
        return self.value

    def get_aliases(self) -> list:
        return list(self.aliases)


def param(value: str, default: _T, aliases: list[str] | None = None) -> _T:
    """Declare a parameter item.

    `@params` **rewrites the class attribute into the resolved literal** at
    import time, so the attribute's post-resolution static type should be
    the literal's type, not `ParamsPath`. Declaring directly with
    `ParamsPath(...)` leaves the static type at `ParamsPath`, and every use
    as a `str` / `int` trips a type error (the repo once had 14 declarations
    and 7 such errors). This wrapper makes the declaration site directly
    carry the right static type while **still returning a `ParamsPath`
    instance at runtime** (the `cast` is a no-op), for `@params` to read the
    path and the default - the configuration mechanism is unchanged.

    Args:
        value: the preferred configuration path, like ``worker:pool:size``
        default: the default used when all candidates are missing; **its
            type is the item's post-resolution static type**
        aliases: fallback configuration paths, in order

    Returns:
        The static type taken from ``default``'s type; at runtime a
        ``ParamsPath`` instance
    """
    return cast("_T", ParamsPath(value=value, default=default, aliases=aliases))
