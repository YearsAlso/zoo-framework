from __future__ import annotations

import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from zoo_framework.statemachine.state_node_type import StateNodeType
from zoo_framework.utils import LogUtils

# The effect executor: module-level shared, lazily built (align-execution-primitives D2).
# Replaces the historical gevent.spawn/joinall: the write path's synchronous
# wait for effects is **deliberately kept** (non-blocking delivery is a
# separately adjudicated behavior decision); only the primitive changes:
# effects run concurrently, waited at most _EFFECT_JOIN_TIMEOUT_SECONDS
# seconds, and the write returns normally after the timeout.
_EFFECT_JOIN_TIMEOUT_SECONDS = 5
_EFFECT_EXECUTOR_WORKERS = 8

_effect_executor: ThreadPoolExecutor | None = None
_effect_executor_lock = threading.Lock()


def _get_effect_executor() -> ThreadPoolExecutor:
    """Get the shared effect executor (double-checked-lock lazy build).

    Never shut down proactively: reclaimed by concurrent.futures' atexit hook
    at interpreter exit; effects are user callbacks and the framework does
    not force-kill them (the greenlet era did not either).
    """
    global _effect_executor
    if _effect_executor is None:
        with _effect_executor_lock:
            if _effect_executor is None:
                _effect_executor = ThreadPoolExecutor(
                    max_workers=_EFFECT_EXECUTOR_WORKERS,
                    thread_name_prefix="zoo-state-effect",
                )
    return _effect_executor


class StateNode:
    """State node."""

    def __init__(self, key: str, value: Any, effect_list: list[types.FunctionType] | None = None):
        # The annotation used to be `list[StateEffect]`, but what actually goes
        # into the list are **functions** (proven both by add_effect's
        # isinstance(effect, types.FunctionType) and by _perform_effect's
        # executor.submit(effect, ...)); and `StateEffect` has no __call__,
        # so that type could never be executed. Changed to the honest
        # `list[types.FunctionType]`.
        self._effect_list: list[types.FunctionType] = []
        self._version = int(time.time())
        self._is_top = False
        self._parent: Any | None = None
        self._children: list[Any] = []
        self._type = StateNodeType.string

        if effect_list is None:
            effect_list = []
        self._value = value
        self._effect_list = effect_list
        self.key = key

    def set_top(self, is_top: bool) -> None:
        """Set whether it is the root node."""
        self._is_top = is_top

    def is_top(self) -> bool:
        """Whether it is the root node."""
        return self._is_top

    def to_be_top(self) -> None:
        """Mark it as the root node."""
        self._is_top = True

    def get_key(self) -> str:
        """Get the state node key."""
        return self.key

    def add_child(self, child: Any) -> None:
        """Add a child node."""
        if child in self._children or child == self:
            return
        self._children.append(child)

    def get_type(self):
        """Get the state node type."""
        return self._type

    def get_value(self) -> Any:
        """Get the state node value."""
        if len(self._children) == 0:
            return self._value
        return self.get_children_value()

    def get_version(self) -> int:
        """Get the state node version.

        版本在每次成功写入后严格递增，可作为乐观并发控制（条件写 CAS）的依据。
        """
        return self._version

    def get_children_value(self) -> dict:
        """Get the children values."""
        _result: dict = {}
        i = 0
        for child in self._children:
            LogUtils.debug(f"${child.get_key}:{child.get_value()}")
            key = child.get_key
            if key is None:
                continue
            if key in _result:
                i += 1
                _result[f"{key}-{i}"] = child.get_value()
            else:
                _result[child.get_key()] = child.get_value()
        return _result

    def set_key(self, key: str) -> None:
        """Set the state node key."""
        self.key = key
        if self._type is StateNodeType.branch:
            self._update_children_key()

    def _update_children_key(self) -> None:
        """Update the children keys."""
        for i, child in enumerate(self._children):
            child.set_key(f"{self.key}.{i}")

    def set_value(self, value: Any) -> None:
        """设置状态节点的值。

        版本**先于 effect 更新**，因此观察者载荷中的 ``version`` 即为写入后的
        新版本。
        """
        self._type = StateNodeType.get_type_by_value(value)
        self._value = value
        version = self._bump_version()
        self._perform_effect(value, version)

    def append_value(self, item: Any) -> None:
        """向集合节点逐条追加一个元素。

        仅接受当前值为 ``list`` 的节点：就地 append（不重建既有元素、不重排），
        随后更新版本并触发 effect。判定以 ``isinstance(get_value(), list)`` 为准，
        与节点的声明类型 ``_type`` 无关——``register_node(key, [..])`` 建出的节点
        ``_type`` 仍是 ``string``，按声明类型判定会误判。非 ``list`` 值（如 ``int``
        或 ``dict`` 子树）明确抛 ``TypeError``，且不覆盖原值。

        Args:
            item: 要追加的元素

        Raises:
            TypeError: 节点当前值不是 ``list``
        """
        current = self.get_value()
        if not isinstance(current, list):
            raise TypeError(
                f"cannot append to non-list state node '{self.key}': "
                f"current value type is {type(current).__name__}"
            )
        current.append(item)
        version = self._bump_version()
        self._perform_effect(current, version)

    def _perform_effect(self, value: Any, version: int) -> None:
        """Perform the state node effects.

        Effects run concurrently on the shared thread executor; the write
        waits synchronously within the timeout. An exception raised by an
        effect does not propagate to the writer but MUST be observable
        (logged).
        """
        if len(self._effect_list) == 0:
            return

        executor = _get_effect_executor()
        futures = [
            executor.submit(effect, {"value": value, "version": version})
            for effect in self._effect_list
        ]
        wait(futures, timeout=_EFFECT_JOIN_TIMEOUT_SECONDS)

        for f in futures:
            if not f.done():
                continue
            # After done(), exception() does not block; like gevent.joinall, it is not re-raised.
            exc = f.exception()
            if exc is not None:
                LogUtils.warning(f"state effect raised an exception: {exc!r}", "StateNode")

    def _bump_version(self) -> int:
        """推进并返回节点版本——每次成功写入都严格递增。

        取 ``max(prev + 1, int(time.time()))``：保留"版本数量级≈墙钟秒"的既有
        观感，仅在"同一秒内多次写"时才与旧值不同；纯计数器会让所有版本值立刻
        变成小整数。严格递增是条件写（CAS）可用的前提——秒级时间戳在同一秒
        重复会导致 ABA 假通过。

        Returns:
            写入后的新版本
        """
        self._version = max(self._version + 1, int(time.time()))
        return self._version

    def get_state(self) -> Any:
        """Get the state node value."""
        return self._value

    def add_effect(self, effect: types.FunctionType | None) -> None:
        """Add an effect to the state node."""
        if effect is None:
            return
        if isinstance(effect, types.FunctionType) and effect not in self._effect_list:
            self._effect_list.append(effect)

    def remove_effect(self, effect: types.FunctionType | None) -> None:
        """Remove an effect from the state node - fixes a memory leak.

        Args:
            effect: the effect function to remove

        Raises:
            ValueError: when the effect is not in the list
        """
        if effect is None:
            return

        try:
            self._effect_list.remove(effect)
            LogUtils.debug(f"✅ Effect removed from state node '{self.key}'")
        except ValueError:
            LogUtils.warning(f"⚠️ Effect not found in state node '{self.key}'")

    def get_children(self) -> list[Any]:
        """Get the children."""
        return self._children

    def __setstate__(self, state: dict) -> None:
        """反序列化兜底：把旧载荷的双版本字段归一为单一 ``_version``。

        改造前的 pickle 载荷同时含 ``version`` 与 ``_version`` 两个键；合并为
        单一 ``_version`` 后，旧存档的 ``version`` 成为冗余字段。此处取其与
        ``_version`` 的较大值，避免版本回退，并使 ``get_version()`` 在旧存档上
        依然可读。

        Args:
            state: pickle 还原出的实例 ``__dict__``
        """
        legacy = state.pop("version", None)
        self.__dict__.update(state)
        current = self.__dict__.get("_version")
        if legacy is not None:
            self.__dict__["_version"] = legacy if current is None else max(current, legacy)
