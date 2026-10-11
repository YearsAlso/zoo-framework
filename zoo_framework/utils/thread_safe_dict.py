import threading
from typing import Any, Generic, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")


# PEP 695 泛型（`class ThreadSafeDict[_K, _V]:`）需要 Python 3.12+，而本项目的下界是 3.11
# （`requires-python`，`[tool.ruff] target-version = "py311"` 跟随它），因此 `Generic`
# 形式是**唯一合法写法**——UP046 不适用，无需抑制。若日后把门槛抬到 3.12+，ruff 会重新要求
# PEP 695，而 pre-commit 钉的 mypy 1.7.1 不支持该语法，那时必须先升级 mypy
# （见 docs/contributing/development.md 的「Python 下界的依据」）。
class ThreadSafeDict(Generic[_K, _V]):
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
