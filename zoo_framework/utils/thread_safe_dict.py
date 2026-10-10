import threading
from typing import Any, Generic, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")


# ruff's UP046 demands the PEP 695 form `class ThreadSafeDict[_K, _V]:`, but **mypy 1.7.1 does
# not yet support PEP 695** ("PEP 695 generics are not yet supported"), and 1.7.1 is both the
# version pinned by pre-commit and the one CI installs. **This is the third time this conflict
# appears in this repo** (the other two: mypy-vs-B010 when installing `__new__` in registry.py,
# mypy-vs-UP047 on params_path.py's `param`) - the common root cause is that **the pinned mypy
# version predates the syntax assumed by the ruff rules this repo enables**. All three resolve
# the same way: a targeted noqa + an in-place explanation; **upgrading mypy resolves all three
# at once** (a dependency change, out of scope).
class ThreadSafeDict(Generic[_K, _V]):  # noqa: UP046 — see above: mypy 1.7.1 does not support PEP 695
    """Thread safe dictionary.

    Lock ownership (align-execution-primitives D3, the same line as #50's
    "thread-safety ownership MUST be declared explicitly"): **one
    `threading.RLock` per instance**. Historically a single module-level
    `multiprocessing.Lock` serialized every instance's reads and writes onto
    the same process-wide lock, measured 2056 ns per op vs 155 ns for the
    thread lock (13x). The lock travels with the instance: when the host
    object is replaced wholesale or the container reset rebuilds the
    instance, its lock changes with it, leaving no process-level shared
    residue; RLock guards against a future same-instance nested call
    deadlocking itself.

    The generic parameterization is a **pure annotation change, no runtime
    effect**: a bare `ThreadSafeDict()` still equals `ThreadSafeDict[Any,
    Any]`, so existing usage is unaffected; while containers **declared
    with type parameters** let `get()` / `pop()` etc. return the real types
    instead of `Any` - all the earlier `no-any-return`s of "returning `Any`
    from a function declaring a concrete return type" stemmed from this.
    """

    def __init__(self, _dict: dict[_K, _V] | None = None):
        if _dict is None:
            _dict = {}
        self._dict: dict[_K, _V] = _dict
        self._lock = threading.RLock()

    def __getstate__(self) -> dict[str, Any]:
        """Exclude the lock when serializing.

        The lock is not data: historically the lock lived at module level and
        instances could be pickled (state-machine persistence relies on
        this); after moving to per-instance locks the persistence path MUST
        keep the same pickle-ability, with a fresh lock rebuilt by
        __setstate__ on load.
        """
        state = self.__dict__.copy()
        state.pop("_lock", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._lock = threading.RLock()

    def __getitem__(self, key: _K) -> _V:
        with self._lock:
            return self._dict[key]

    def __setitem__(self, key: _K, value: _V) -> None:
        with self._lock:
            self._dict[key] = value

    def __delitem__(self, key: _K) -> None:
        with self._lock:
            del self._dict[key]

    def __len__(self) -> int:
        with self._lock:
            return len(self._dict)

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._dict

    def keys(self) -> list[_K]:
        with self._lock:
            return list(self._dict.keys())

    def values(self) -> list[_V]:
        with self._lock:
            return list(self._dict.values())

    def items(self) -> list[tuple[_K, _V]]:
        with self._lock:
            return list(self._dict.items())

    def get(self, handler_name: _K) -> _V | None:
        with self._lock:
            return self._dict.get(handler_name)

    def has_key(self, key: _K) -> bool:
        with self._lock:
            return key in self._dict

    def pop(self, key: _K) -> _V:
        with self._lock:
            return self._dict.pop(key)

    def clear(self) -> None:
        """Clear the contents."""
        with self._lock:
            self._dict.clear()

    def get_values(self) -> list[_V]:
        with self._lock:
            return list(self._dict.values())

    def get_keys(self) -> list[_K]:
        with self._lock:
            return list(self._dict.keys())
