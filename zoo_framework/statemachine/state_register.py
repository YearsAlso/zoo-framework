import copy
import time
from typing import Any

from statemachine.state_node_type import StateNodeType
from zoo_framework.core.thread_safe_dict import ThreadSafeDict
from zoo_framework.statemachine.state_node import StateNode
from zoo_framework.utils import LogUtils


class StateRegister:
    """
    状态节点注册器
    """
    _state_index_map: ThreadSafeDict = {}

    def __init__(self):
        """
        初始化状态节点注册器
        """
        self._state_index_map = ThreadSafeDict()

    def register_top_node(self, key: str, value: Any, effect: list = None):
        """
        注册根节点
        """
        node = StateNode(key, value, effect)
        self._state_index_map[node.get_key()] = node
        node.to_be_top()

    def register_node(self, key: str, value: Any, effect: list = None):
        """
        注册状态节点
        """
        node = StateNode(key, value, effect)
        self._state_index_map[node.get_key()] = node

    def set_state(self, key: str, value: Any, effect: list = None):
        """
        设置状态节点的值
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

        # TODO: 如果是字典类型,
        if StateNodeType.get_type_by_value(value) == StateNodeType.branch:
            for k, v in value.items():
                self.set_state(f"{key}.{k}", v, effect)
            return
        else:
            node = self.get_state_node(key)
            if node is None:
                self.register_node(key, value, effect)
            else:
                node.set_value(value)

    def update_state_node(self, key: str, node: StateNode):
        """
        更新状态节点
        """
        self._state_index_map[key] = node

    def _check_children(self, key: str):
        pass

    def _check_and_build_tree(self, key_queue):
        """
        检查并构建树型结构
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
            node.add_child(children_node)

    def get_state_node(self, key: str) -> StateNode:
        """
        获取状态节点
        """
        return self._state_index_map.get(key)

    def get_state_value(self, key: str) -> Any:
        """
        获取状态节点的值
        """
        node = self.get_state_node(key)
        if node is None:
            return None
        return node.get_value()

    def get_state_children_value(self, key: str) -> Any:
        """
        获取状态节点的子节点的值
        """
        node = self.get_state_node(key)
        if node is None:
            return None
        return node.get_children_value()

    def move_state_node(self, key: str, target_key: str):
        """
        移动状态节点
        """
        node = self.get_state_node(key)
        if node is None:
            LogUtils.error(self.__class__, f"State is not exist, key: {key}")
            return

        node.set_key(target_key)
        self.set_state(target_key, node)
        # TODO: 删除子节点
        self.delete_state_node(key)

    def delete_state_node(self, key: str):
        """
        删除状态节点
        """
        node = self.get_state_node(key)
        if node is None:
            LogUtils.error(self.__class__, f"State is not exist, key: {key}")
            return

        if node.get_type() == StateNodeType.branch:
            # 如果是分支节点，删除所有子节点
            for child in node.get_children():
                self.delete_state_node(child.get_key())

        self.set_state(key, None)

    def copy_state_node(self, key: str, target_key: Any):
        """
        复制状态节点的值
        """
        node = self.get_state_node(key)
        if node is None:
            return
        new_node = copy.deepcopy(node)
        new_node.set_key(target_key)
        self.set_state(target_key, new_node)
