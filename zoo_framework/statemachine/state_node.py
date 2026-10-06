from __future__ import annotations

import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from zoo_framework.statemachine.state_node_type import StateNodeType
from zoo_framework.utils import LogUtils

# effect 执行器：模块级共享、懒建（align-execution-primitives D2）。
# 替代历史的 gevent.spawn/joinall：写路径同步等待 effect 的语义**刻意保留**
# （非阻塞投递属另行裁定的行为决策），换的只是原语：effect 并发执行、
# 最长等 _EFFECT_JOIN_TIMEOUT_SECONDS 秒、超时后写入正常返回。
_EFFECT_JOIN_TIMEOUT_SECONDS = 5
_EFFECT_EXECUTOR_WORKERS = 8

_effect_executor: ThreadPoolExecutor | None = None
_effect_executor_lock = threading.Lock()


def _get_effect_executor() -> ThreadPoolExecutor:
    """取共享 effect 执行器（双检锁懒建）.

    不主动 shutdown：解释器退出时由 concurrent.futures 的 atexit 钩子回收；
    effect 是用户回调，框架不做强杀（greenlet 时代同样不强杀）。
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
    """状态节点."""

    def __init__(self, key: str, value: Any, effect_list: list[types.FunctionType] | None = None):
        # 注解原为 `list[StateEffect]`，但代码往列表里存的是**函数**（`add_effect` 的
        # `isinstance(effect, types.FunctionType)` 与 `_perform_effect` 里的 `executor.submit(effect, …)`
        # 都证明了这点）；而 `StateEffect` **没有 `__call__`**，那个类型根本不可能被执行。
        # 故改为如实的 `list[types.FunctionType]`。
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
        """设置是否是根节点."""
        self._is_top = is_top

    def is_top(self) -> bool:
        """是否是根节点."""
        return self._is_top

    def to_be_top(self) -> None:
        """设置为根节点."""
        self._is_top = True

    def get_key(self) -> str:
        """获取状态节点的key."""
        return self.key

    def add_child(self, child: Any) -> None:
        """添加子节点."""
        if child in self._children or child == self:
            return
        self._children.append(child)

    def get_type(self):
        """获取状态节点的类型."""
        return self._type

    def get_value(self) -> Any:
        """获取状态节点的值."""
        if len(self._children) == 0:
            return self._value
        return self.get_children_value()

    def get_children_value(self) -> dict:
        """获取子节点的值."""
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
        """设置状态节点的key."""
        self.key = key
        if self._type is StateNodeType.branch:
            self._update_children_key()

    def _update_children_key(self) -> None:
        """更新子节点的 key."""
        for i, child in enumerate(self._children):
            child.set_key(f"{self.key}.{i}")

    def set_value(self, value: Any) -> None:
        """设置状态节点的值."""
        version = int(time.time())
        self._type = StateNodeType.get_type_by_value(value)
        self._value = value
        self._update_version()
        self._perform_effect(value, version)

    def _perform_effect(self, value: Any, version: int) -> None:
        """执行状态节点的副作用.

        effect 在共享线程执行器上并发执行；写入在超时内同步等待。
        effect 抛出的异常不传播给写入方，但 MUST 可观测（记入日志）。
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
            # done() 后取 exception() 不阻塞；与 gevent.joinall 一致不重抛。
            exc = f.exception()
            if exc is not None:
                LogUtils.warning(f"状态 effect 执行抛出异常: {exc!r}", "StateNode")

    def _update_version(self) -> None:
        """更新状态节点的版本号."""
        self.version = int(time.time())

    def get_state(self) -> Any:
        """获取状态节点的值."""
        return self._value

    def add_effect(self, effect: types.FunctionType | None) -> None:
        """添加状态节点的副作用."""
        if effect is None:
            return
        if isinstance(effect, types.FunctionType) and effect not in self._effect_list:
            self._effect_list.append(effect)

    def remove_effect(self, effect: types.FunctionType | None) -> None:
        """移除状态节点的副作用 - 修复内存泄漏.

        Args:
            effect: 要移除的副作用函数

        Raises:
            ValueError: 如果 effect 不在列表中
        """
        if effect is None:
            return

        try:
            self._effect_list.remove(effect)
            LogUtils.debug(f"✅ Effect removed from state node '{self.key}'")
        except ValueError:
            LogUtils.warning(f"⚠️ Effect not found in state node '{self.key}'")

    def get_children(self) -> list[Any]:
        """获取子节点."""
        return self._children
