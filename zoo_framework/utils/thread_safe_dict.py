import threading
from typing import Any, Generic, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")


# ruff 的 UP046 要求改用 PEP 695 的 `class ThreadSafeDict[_K, _V]:`，但 **mypy 1.7.1 尚不支持
# PEP 695**（"PEP 695 generics are not yet supported"），而 1.7.1 既是 pre-commit 钉住的版本、
# 也是 CI 安装的那版。**这是同一冲突在本仓库的第三次**（另两处：`registry.py` 装 `__new__` 时
# mypy↔B010、`params_path.py` 的 `param` 上 mypy↔UP047）—— 共同根因是**钉住的 mypy 版本低于
# 本仓库启用的 ruff 规则所假定的语法**。三处都用"定向 noqa + 就地说明"解决；**升级 mypy 可一次
# 解掉全部三处**（属依赖变更，不在本变更范围）。
class ThreadSafeDict(Generic[_K, _V]):  # noqa: UP046 — 见上：mypy 1.7.1 不支持 PEP 695
    """Thread safe dictionary.

    锁归属（align-execution-primitives D3，与 #50 的「线程安全归属 MUST 显式
    声明」同一条线）：**每实例一把 `threading.RLock`**。历史上是模块级单把
    `multiprocessing.Lock`——它把所有实例的读写串行化到同一把全进程锁上，实测
    单次操作 2056 ns vs 线程锁 155 ns（13x）。锁随实例走：实例被整体替换
    （如 tests/conftest.py 对 `reactor_map` / `_channel_map` 的复位）时其锁随之
    更替，不残留进程级共享；选 RLock 是为防未来同实例嵌套调用自我死锁。

    泛型参数化是**纯注解改动、运行期无变化**：裸写 `ThreadSafeDict()` 仍等价于
    `ThreadSafeDict[Any, Any]`，故既有用法不受影响；而**声明时给出类型参数**的那些容器
    就能让 `get()` / `pop()` 等返回真实类型，而不是 `Any` —— 此前所有"从声明为具体返回类型
    的函数里返回 `Any`"的 `no-any-return` 都源于此。
    """

    def __init__(self, _dict: dict[_K, _V] | None = None):
        if _dict is None:
            _dict = {}
        self._dict: dict[_K, _V] = _dict
        self._lock = threading.RLock()

    def __getstate__(self) -> dict[str, Any]:
        """序列化时剔除锁.

        锁不是数据：历史上锁在模块级，实例可被 pickle（状态机持久化依赖这一点）；
        改为实例持锁后 MUST 在持久化路径上保持同等的可 pickle 性，
        载入时由 __setstate__ 重建新锁。
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
        """清空内容."""
        with self._lock:
            self._dict.clear()

    def get_values(self) -> list[_V]:
        with self._lock:
            return list(self._dict.values())

    def get_keys(self) -> list[_K]:
        with self._lock:
            return list(self._dict.keys())
