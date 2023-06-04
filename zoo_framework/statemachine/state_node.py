import time
import types
from typing import Any

import gevent

from zoo_framework.statemachine.state_node_type import StateNodeType


class StateNode(object):
    """
    状态节点
    """
    _effect = []
    _version = time.time()
    _is_top = False
    _parent: Any = None
    _children: list[Any] = []
    _type = StateNodeType.string

    def __init__(self, key, value, effect=None):
        if effect is None:
            effect = []
        self._value = value
        self._effect = effect
        self.key = key

    def set_top(self, is_top: bool):
        """
        设置是否是根节点
        """
        self._is_top = is_top

    def to_be_top(self):
        """
        设置为根节点
        """
        self._is_top = True

    def get_key(self):
        """
        获取状态节点的key
        """
        return self.key

    def add_child(self, child: Any):
        """
        添加子节点
        """
        self._children.append(child)

    def get_type(self):
        """
        获取状态节点的类型
        """
        return self._type

    def get_value(self) -> Any:
        """
        获取状态节点的值
        """
        if len(self._children) == 0:
            return self._value
        else:
            return self.get_children_value()

    def get_children_value(self):
        """
        获取子节点的值
        """
        _result = {}
        for i, child in self._children:
            print(f"${child.get_key}:{child.get_value()}")
            key = child.get_key
            if key is None:
                continue
            if key in _result.keys():
                _result[f"{key}-{i}"] = child.get_value()
            else:
                _result[child.get_key()] = child.get_value()
        return _result

    def set_key(self, key):
        """
        设置状态节点的key
        """
        self.key = key
        if self._type is StateNodeType.branch:
            self._update_children_key()

    def _update_children_key(self):
        """
        更新子节点的 key
        """
        for i, child in self._children:
            child.set_key(f"{self.key}.{i}")

    def set_state(self, state):
        """
        设置状态节点的值
        """
        StateNodeType.get_type_by_value(state)
        self._value = state
        self._update_version()
        self._perform_effect()

    def _perform_effect(self):
        """
        执行状态节点的副作用
        """
        effect_queue = []
        for effect in self._effect:
            g = gevent.spawn(effect)
            effect_queue.append(g)

        gevent.joinall(effect_queue, timeout=5)

    def _update_version(self):
        """
        更新状态节点的版本号
        """
        self.version = time.time()

    def get_state(self):
        """
        获取状态节点的值
        """
        return self._value
