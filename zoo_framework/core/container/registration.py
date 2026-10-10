"""A registration.

A registration records "how to build an instance of a type, which scope it
belongs to, and its thread-safety ownership". The id is taken as **module +
qualified name** rather than the bare class name (see design D2): the bare
name would let two same-named classes defined in different places overwrite
each other, silently, when resolving to the wrong object.

The type contract is guarded by this object: ``registered_type`` is always
the class provided at registration; the container neither replaces it nor
returns a proxy, so ``isinstance`` / ``issubclass`` keep working as usual.
"""

from collections.abc import Callable
from typing import Any


def qualified_name(cls: type) -> str:
    """Get the process-unique identity of a type (module + qualified name).

    Args:
        cls: the class to identify

    Returns:
        An identity like ``pkg.mod.Outer.Inner``

    Raises:
        TypeError: the argument is not a class
    """
    if not isinstance(cls, type):
        raise TypeError(f"registration id can only be derived from a class, got {cls!r}")
    return f"{cls.__module__}.{cls.__qualname__}"


class Registration:
    """A registration.

    Attributes:
        name: the registration id (unique within the process)
        registered_type: the type given at registration; carries the type
            contract, may be None (when registered by name)
        scope_kind: which scope kind it belongs to
        thread_safety: the thread-safety ownership declaration
        explicit_name: whether the id was given explicitly (rather than
            derived from the class)
        on_release: the release hook called when the instance is released;
            signature ``(instance) -> None``
    """

    __slots__ = (
        "explicit_name",
        "factory",
        "name",
        "on_release",
        "registered_type",
        "scope_kind",
        "thread_safety",
    )

    def __init__(
        self,
        name: str,
        registered_type: type | None,
        factory: Callable[[], Any],
        scope_kind: str,
        thread_safety: str,
        explicit_name: bool = False,
        on_release: Callable[[Any], None] | None = None,
    ):
        self.name = name
        self.registered_type = registered_type
        self.factory = factory
        self.scope_kind = scope_kind
        self.thread_safety = thread_safety
        self.explicit_name = explicit_name
        self.on_release = on_release

    def create(self) -> Any:
        """Build one instance in the way given at registration."""
        return self.factory()

    def __repr__(self) -> str:
        return (
            f"Registration(name={self.name!r}, scope={self.scope_kind!r}, "
            f"thread_safety={self.thread_safety!r})"
        )
