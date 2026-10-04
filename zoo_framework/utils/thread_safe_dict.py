from multiprocessing import Lock
from typing import Generic, TypeVar

_K = TypeVar("_K")
_V = TypeVar("_V")

_lock = Lock()


# ruff 的 UP046 要求改用 PEP 695 的 `class ThreadSafeDict[_K, _V]:`，但 **mypy 1.7.1 尚不支持
# PEP 695**（"PEP 695 generics are not yet supported"），而 1.7.1 既是 pre-commit 钉住的版本、
# 也是 CI 安装的那版。**这是同一冲突在本仓库的第三次**（另两处：`registry.py` 装 `__new__` 时
# mypy↔B010、`params_path.py` 的 `param` 上 mypy↔UP047）—— 共同根因是**钉住的 mypy 版本低于
# 本仓库启用的 ruff 规则所假定的语法**。三处都用"定向 noqa + 就地说明"解决；**升级 mypy 可一次
# 解掉全部三处**（属依赖变更，不在本变更范围）。
class ThreadSafeDict(Generic[_K, _V]):  # noqa: UP046 — 见上：mypy 1.7.1 不支持 PEP 695
    """Thread safe dictionary.

    泛型参数化是**纯注解改动、运行期无变化**：裸写 `ThreadSafeDict()` 仍等价于
    `ThreadSafeDict[Any, Any]`，故既有用法不受影响；而**声明时给出类型参数**的那些容器
    就能让 `get()` / `pop()` 等返回真实类型，而不是 `Any` —— 此前所有"从声明为具体返回类型
    的函数里返回 `Any`"的 `no-any-return` 都源于此。
    """

    def __init__(self, _dict: dict[_K, _V] | None = None):
        if _dict is None:
            _dict = {}
        self._dict: dict[_K, _V] = _dict

    def __getitem__(self, key: _K) -> _V:
        with _lock:
            return self._dict[key]

    def __setitem__(self, key: _K, value: _V) -> None:
        with _lock:
            self._dict[key] = value

    def __delitem__(self, key: _K) -> None:
        with _lock:
            del self._dict[key]

    def __len__(self) -> int:
        with _lock:
            return len(self._dict)

    def __contains__(self, key: object) -> bool:
        with _lock:
            return key in self._dict

    def keys(self) -> list[_K]:
        with _lock:
            return list(self._dict.keys())

    def values(self) -> list[_V]:
        with _lock:
            return list(self._dict.values())

    def items(self) -> list[tuple[_K, _V]]:
        with _lock:
            return list(self._dict.items())

    def get(self, handler_name: _K) -> _V | None:
        with _lock:
            return self._dict.get(handler_name)

    def has_key(self, key: _K) -> bool:
        with _lock:
            return key in self._dict

    def pop(self, key: _K) -> _V:
        with _lock:
            return self._dict.pop(key)

    def clear(self) -> None:
        """清空内容."""
        with _lock:
            self._dict.clear()

    def get_values(self) -> list[_V]:
        with _lock:
            return list(self._dict.values())

    def get_keys(self) -> list[_K]:
        with _lock:
            return list(self._dict.keys())
