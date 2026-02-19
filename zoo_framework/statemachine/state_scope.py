"""state_scope - zoo_framework/statemachine/state_scope.py

模块功能描述:
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

import copy
from typing import Any

from zoo_framework.statemachine.state_index_factory import StateIndex, StateIndexFactory
from zoo_framework.statemachine.state_node import StateNode
from zoo_framework.statemachine.state_node_type import StateNodeType
from zoo_framework.utils import LogUtils


class StateScope:
    """状态域 - P2 优化版本.

    P2 优化:
    1. 使用工厂模式创建索引
    2. 支持多种索引实现
    3. 支持动态切换索引类型

    Attributes:
        _state_index: 状态节点索引
    """

    def __init__(self, index_type: str = "dict"):
        """初始化状态域.

        P2 优化:使用工厂模式创建索引

        Args:
            index_type: 索引类型（"dict" 或 "hierarchical"）
        """
        # P2 优化:使用工厂模式创建索引
        self._state_index: StateIndex = StateIndexFactory.create_index(index_type)

    def observe_state_node(self, key: str, effect: Any) -> None:
        """观察状态节点.

        Args:
            key: 状态键名
            effect: 观察者回调
        """
        node = self.get_state_node(key)
        if node is None:
            return
        node.add_effect(effect)

    def unobserve_state_node(self, key: str, effect: Any) -> None:
        """移除状态节点观察者 - 修复内存泄漏.

        Args:
            key: 状态键名
            effect: 观察者回调函数

        Raises:
            KeyError: 如果状态节点不存在
        """
        node = self.get_state_node(key)
        if node is None:
            raise KeyError(f"State node '{key}' not found")
        node.remove_effect(effect)

    def register_top_node(self, key: str, value: Any, effect: list | None = None) -> None:
        """注册根节点.

        Args:
            key: 节点键名
            value: 节点值
            effect: 副作用列表
        """
        node = StateNode(key, value, effect)
        self._state_index.set(node.get_key(), node)
        node.to_be_top()

    def register_node(self, key: str, value: Any, effect: list | None = None) -> None:
        """注册状态节点.

        Args:
            key: 节点键名
            value: 节点值
            effect: 副作用列表
        """
        if len(key.split(".")) == 1:
            self.register_top_node(key, value, effect)
            return

        node = StateNode(key, value, effect)
        self._state_index.set(node.get_key(), node)

    def set_state_node(self, key: str, value: Any, effect: list | None = None) -> None:
        """设置状态节点的值.

        Args:
            key: 节点键名
            value: 节点值
            effect: 副作用列表
        """
        # 1.节点拆分
        key_queue = key.split(".")

        if len(key_queue) > 1:
            self._check_and_build_tree(key_queue)
        else:
            # 如果是根节点，直接注册
            node = self.get_state_node(key)
            if node is None:
                self.register_node(key, value)
            return

        if StateNodeType.get_type_by_value(value) == StateNodeType.branch:
            for k, v in value.items():
                self.set_state_node(f"{key}.{k}", v, effect)
            return
        node = self.get_state_node(key)
        if node is None:
            self.register_node(key, value, effect)
        else:
            node.set_value(value)

    def update_state_node(self, key: str, node: StateNode) -> None:
        """更新状态节点.

        Args:
            key: 节点键名
            node: 状态节点
        """
        self._state_index.set(key, node)

    def _check_children(self, key: str) -> None:
        """检查子节点."""
        pass

    def _check_and_build_tree(self, key_queue: list[str]) -> None:
        """检查并构建树型结构.

        Args:
            key_queue: 键队列
        """
        # 2. 依次创建节点
        current_key = key_queue[0]
        for i in range(len(key_queue)):
            if i != 0:
                current_key = f"{current_key}.{key_queue[i]}"
            if self.get_state_node(current_key) is None:
                self.register_node(current_key, None)

        #  3. 设置树型结构
        current_key = key_queue[0]
        for i in range(1, len(key_queue)):
            node: StateNode = self.get_state_node(current_key)
            children_node: StateNode = self.get_state_node(f"{current_key}.{key_queue[i]}")

            # 一种key不能重复添加
            node.add_child(children_node)

    def get_state_node(self, key: str) -> StateNode | None:
        """获取状态节点.

        Args:
            key: 节点键名

        Returns:
            状态节点或 None
        """
        return self._state_index.get(key)

    def get_state_value(self, key: str) -> Any:
        """获取状态节点的值.

        Args:
            key: 节点键名

        Returns:
            节点值
        """
        node = self.get_state_node(key)
        if node is None:
            return None
        return node.get_value()

    def get_state_children_value(self, key: str) -> Any:
        """获取状态节点的子节点的值.

        Args:
            key: 节点键名

        Returns:
            子节点值字典
        """
        node = self.get_state_node(key)
        if node is None:
            return None
        return node.get_children_value()

    def move_state_node(self, key: str, target_key: str) -> None:
        """移动状态节点.

        Args:
            key: 原键名
            target_key: 目标键名
        """
        node = self.get_state_node(key)
        if node is None:
            LogUtils.error(self.__class__, f"State is not exist, key: {key}")
            return

        node.set_key(target_key)
        self.set_state_node(target_key, node)
        # 删除子节点
        self.remove_state_node(key)

    def remove_state_node(self, key: str) -> None:
        """删除状态节点.

        Args:
            key: 节点键名
        """
        node = self.get_state_node(key)
        if node is None:
            LogUtils.error(self.__class__, f"State is not exist, key: {key}")
            return

        if node.get_type() == StateNodeType.branch:
            # 如果是分支节点，删除所有子节点
            for child in node.get_children():
                self.remove_state_node(child.get_key())

        self.set_state_node(key, None)

    def copy_state_node(self, key: str, target_key: Any) -> None:
        """复制状态节点的值.

        Args:
            key: 原键名
            target_key: 目标键名
        """
        node = self.get_state_node(key)
        if node is None:
            return
        new_node = copy.deepcopy(node)
        new_node.set_key(target_key)
        self.set_state_node(target_key, new_node)

    def get_all_nodes(self) -> dict:
        """获取所有状态节点.

        P2 优化:支持获取所有节点

        Returns:
            节点字典
        """
        return self._state_index.get_all()

    def find_nodes_by_prefix(self, prefix: str) -> list:
        """根据前缀查找节点.

        P2 优化:支持前缀查找

        Args:
            prefix: 键前缀

        Returns:
            节点列表
        """
        return self._state_index.find_by_prefix(prefix)


# 导出公共 API
__all__ = ["StateScope"]


def get_state_scope(index_type: str = "dict") -> StateScope:
    """获取全局状态域."""
    return StateScope(index_type)
