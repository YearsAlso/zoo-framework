from __future__ import annotations

import time
import types
from typing import TYPE_CHECKING, Any

import gevent

from zoo_framework.statemachine.state_node_type import StateNodeType
from zoo_framework.utils import LogUtils

if TYPE_CHECKING:
    from .state_effect import StateEffect


class StateNode:
    """状态节点."""

    def __init__(self, key: str, value: Any, effect_list: list[StateEffect] | None = None):
        self._effect_list: list[StateEffect] = []
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
        """执行状态节点的副作用."""
        if len(self._effect_list) == 0:
            return

        g_effect_queue = []
        for effect in self._effect_list:
            g = gevent.spawn(effect, {"value": value, "version": version})
            g_effect_queue.append(g)

        gevent.joinall(g_effect_queue, timeout=5)

    def _update_version(self) -> None:
        """更新状态节点的版本号."""
        self.version = int(time.time())

    def get_state(self) -> Any:
        """获取状态节点的值."""
        return self._value

    def add_effect(self, effect: types.FunctionType) -> None:
        """添加状态节点的副作用."""
        if effect is None:
            return
        if isinstance(effect, types.FunctionType) and effect not in self._effect_list:
            self._effect_list.append(effect)

    def remove_effect(self, effect: types.FunctionType) -> None:
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
