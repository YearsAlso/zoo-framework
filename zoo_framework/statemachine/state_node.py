import time
import types
from typing import Any

import gevent

from zoo_framework.utils import LogUtils
from zoo_framework.statemachine.state_node_type import StateNodeType


class StateNode(object):
    """
    状态节点
    """

    def __init__(self, key, value, effect_list=None):
        self._effect_list: list[types.FunctionType] = []
        self._version = int(time.time())
        self._is_top = False
        self._parent: Any = None
        self._children: list[Any] = []
        self._type = StateNodeType.string

        if effect_list is None:
            effect_list = []
        self._value = value
        self._effect_list = effect_list
        self.key = key

    def set_top(self, is_top: bool):
        """
        设置是否是根节点
        """
        self._is_top = is_top

    def is_top(self):
        """
        是否是根节点
        """
        return self._is_top

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
        if child in self._children or child == self:
            return
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
        i = 0
        for child in self._children:
            LogUtils.debug(f"${child.get_key}:{child.get_value()}")
            key = child.get_key
            if key is None:
                continue
            if key in _result.keys():
                i += 1
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

    def set_value(self, value):
        """
        设置状态节点的值
        """
        version = int(time.time())
        self._type = StateNodeType.get_type_by_value(value)
        self._value = value
        self._update_version()
        self._perform_effect(value, version)

    def _perform_effect(self, value, version):
        """
        执行状态节点的副作用
        """
        if len(self._effect_list) == 0:
            return

        g_effect_queue = []
        for effect in self._effect_list:
            g = gevent.spawn(effect, {"value": value, "version": version})
            g_effect_queue.append(g)

        gevent.joinall(g_effect_queue, timeout=5)

    def _update_version(self):
        """
        更新状态节点的版本号
        """
        self.version = int(time.time())

    def get_state(self):
        """
        获取状态节点的值
        """
        return self._value

    def add_effect(self, effect: types.FunctionType):
        """
        添加状态节点的副作用
        """
        if effect is None:
            return
        if isinstance(effect, types.FunctionType) and effect not in self._effect_list:
            self._effect_list.append(effect)

    def get_children(self) -> list[Any]:
        """
        获取子节点
        """
        return self._children
