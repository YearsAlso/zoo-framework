"""The framework's own process-level sharing registry.

Objects the framework needs to share at process level (the various managers)
register here as a **process scope**, instead of relying on the implicit
global singleton style of ``@cage``, which replaced the class with a
decorator.

``@cage``'s two sins were: **replacing the class** (so ``issubclass`` /
``isinstance`` both broke) and **keying on the bare class name** (so two
same-named classes overwrote each other). ``process_scoped`` commits neither:
the class remains a real class, the key is module + qualified name, and
"process-level" is a **declared** fact - able to be ``reset()``-ed,
``replace()``-d, and looked up from the container.

The difference from "external users registering themselves" is merely
convenience: this wraps the scope handle and construction details so the
caller writes a one-line decorator, and ``X()`` still returns the
process-level instance (call sites unchanged).
"""

from collections.abc import Callable
from typing import Any

from .container import ScopedContainer
from .scope import Scope, ScopeKind

# The framework's own process-level container. External users may build their
# own containers; this one serves the framework internals only.
_process_container = ScopedContainer()


def framework_container() -> ScopedContainer:
    """The framework's own process-level container (for diagnostics and test isolation)."""
    return _process_container


def register_process_instance(
    cls: type,
    *,
    thread_safety: str,
    factory: Callable[[], Any] | None = None,
    on_release: Callable[[Any], None] | None = None,
) -> str:
    """Register ``cls`` as a process-level shared item.

    Args:
        cls: the class to register
        thread_safety: the thread-safety ownership declaration, see
            ``ThreadSafety``; **required**
        factory: a custom construction method; by default calls ``cls()``
        on_release: an optional release hook

    Returns:
        The registration key (module + qualified name)
    """
    return _process_container.register(
        cls,
        scope_kind=ScopeKind.PROCESS,
        thread_safety=thread_safety,
        factory=factory,
        on_release=on_release,
    )


def process_instance(cls: type) -> Any:
    """Get the ``cls`` instance in the process scope."""
    return _process_container.resolve(cls, Scope.process())


def process_scoped(
    *, thread_safety: str, on_release: Callable[[Any], None] | None = None
) -> Callable[[type], type]:
    """Class decorator: the class itself is unchanged, but ``cls()`` returns the sole instance in the process scope.

    **Does not replace the class** - this is the dividing line from ``@cage``,
    so ``issubclass(cls, X)`` and ``isinstance(obj, cls)`` both keep working.

    Three implementation details, all forced by CPython's behavior:

    1. Since ``__new__`` returns an instance of ``cls``, ``type.__call__``
       **still calls ``__init__`` once on it**. So ``__init__`` is wrapped to
       be idempotent: only the first call actually executes. Otherwise a
       class with instance state like ``StateMachineManager`` would have its
       state reset by the second call.
    2. The container's construction **must bypass** ``__new__`` (build the
       object with ``original_new``), otherwise "factory -> ``cls()`` ->
       ``__new__`` -> resolve" would recurse back into the container itself.
    3. Subclasses do **not** inherit the process-level identity: when
       ``subcls is not cls``, normal construction applies. Otherwise
       decorating a base class once would turn all of its subclasses into the
       same shared instance.

    Args:
        thread_safety: the thread-safety ownership declaration, see
            ``ThreadSafety``; **required**
        on_release: an optional release hook

    Returns:
        A class decorator that preserves the class identity
    """

    def decorate(cls: type) -> type:
        # The group of operations below is "dynamically rewriting the class"
        # itself (the very point of this module): first capture the original
        # `__new__` / `__init__`, then swap in forwarding versions. Static
        # checking cannot model it - reading `cls.__init__` is judged
        # unsound, and `original_new(cls)` falls outside typeshed's
        # overloads. So use **targeted ignores** (each with its error code)
        # and state the reason, instead of degrading to a cast that papers
        # over them: an ignore at least puts "checking is bypassed here" in
        # the open.
        original_new = cls.__new__
        original_init = cls.__init__  # type: ignore[misc]

        def _guarded_init(self, *args, **kwargs):
            if getattr(self, "_scoped_ready", False):
                return
            original_init(self, *args, **kwargs)
            self._scoped_ready = True

        def _delegating_new(subcls, *args, **kwargs):
            if subcls is not cls:
                return original_new(subcls, *args, **kwargs)
            return process_instance(cls)

        def _build():
            obj = original_new(cls)  # type: ignore[call-overload]
            _guarded_init(obj)
            return obj

        cls.__init__ = _guarded_init  # type: ignore[misc]
        # This line is constrained by two tools that demand opposite things:
        # mypy flags a direct assignment as a type mismatch (typeshed marks
        # `__new__` as an overloaded function), while changing to
        # setattr(cls, "__new__", ...) gets blocked by ruff's B010 (do not use
        # setattr with constant attribute names). The two cannot both be
        # satisfied, so keep the direct assignment with a **targeted** ignore -
        # this is an "explainable exception", not papering over a fixable
        # problem: it suppresses the opposition between the two tools, not a
        # mismatch that could be fixed.
        cls.__new__ = staticmethod(_delegating_new)  # type: ignore[assignment]
        register_process_instance(
            cls, thread_safety=thread_safety, factory=_build, on_release=on_release
        )
        return cls

    return decorate
