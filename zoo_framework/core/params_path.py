from typing import TypeVar, cast

# ruff's UP047 demands the PEP 695 form `def param[T](...)`, but **mypy 1.7.1
# does not yet support PEP 695** (it reports "PEP 695 generics are not yet
# supported") - and 1.7.1 is both the version pinned by pre-commit and the
# one CI installs. The two tools demand opposite things, hence keep the
# TypeVar form with a targeted noqa here, instead of letting either fail.
# Upgrading mypy would resolve it (a dependency change, out of scope).
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


def param(  # noqa: UP047 — 见文件头说明：mypy 1.7.1 不支持 PEP 695，两个工具要求相反
    value: str, default: _T, aliases: list[str] | None = None
) -> _T:
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
