"""状态节点索引工厂.

P2 优化：将索引创建优化为工厂模式
索引设置为对象，支持多种实现方式
"""

from abc import ABC, abstractmethod
from typing import Any

from zoo_framework.statemachine.state_node import StateNode
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


class StateIndex(ABC):
    """状态索引抽象基类.

    P2 优化：定义状态索引的接口
    """

    @abstractmethod
    def get(self, key: str) -> StateNode | None:
        """根据 key 获取状态节点."""
        pass

    @abstractmethod
    def set(self, key: str, node: StateNode) -> None:
        """设置状态节点."""
        pass

    @abstractmethod
    def remove(self, key: str) -> StateNode | None:
        """移除状态节点."""
        pass

    @abstractmethod
    def has(self, key: str) -> bool:
        """检查是否存在."""
        pass

    @abstractmethod
    def get_all(self) -> dict[str, StateNode]:
        """获取所有节点."""
        pass

    @abstractmethod
    def find_by_prefix(self, prefix: str) -> list[StateNode]:
        """根据前缀查找节点."""
        pass


class ThreadSafeDictIndex(StateIndex):
    """线程安全字典索引.

    基于 ThreadSafeDict 的索引实现
    """

    def __init__(self):
        self._index = ThreadSafeDict()

    def get(self, key: str) -> StateNode | None:
        return self._index.get(key)

    def set(self, key: str, node: StateNode) -> None:
        self._index[key] = node

    def remove(self, key: str) -> StateNode | None:
        if key in self._index:
            node = self._index[key]
            del self._index[key]
            return node
        return None

    def has(self, key: str) -> bool:
        return key in self._index

    def get_all(self) -> dict[str, StateNode]:
        return dict(self._index)

    def find_by_prefix(self, prefix: str) -> list[StateNode]:
        """根据前缀查找节点."""
        result: list[StateNode] = []
        for key, node in self._index.items():
            if key.startswith(prefix):
                result.append(node)
        return result


class HierarchicalIndex(StateIndex):
    """分层索引.

    按层级组织索引，支持更快的树形查找
    """

    def __init__(self):
        self._root: dict = {}
        self._cache: dict = {}

    def _split_key(self, key: str) -> list[str]:
        """分割 key."""
        return key.split(".")

    def get(self, key: str) -> StateNode | None:
        # 先查缓存
        if key in self._cache:
            return self._cache[key]

        # 遍历层级
        parts = self._split_key(key)
        current = self._root

        for part in parts:
            if part not in current:
                return None
            current = current[part]

        if isinstance(current, StateNode):
            self._cache[key] = current
            return current
        return None

    def set(self, key: str, node: StateNode) -> None:
        parts = self._split_key(key)
        current = self._root

        # 创建层级结构
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = node
        self._cache[key] = node

    def remove(self, key: str) -> StateNode | None:
        node = self.get(key)
        if node is None:
            return None

        # 从缓存中移除
        if key in self._cache:
            del self._cache[key]

        # 从层级结构中移除
        parts = self._split_key(key)
        current = self._root

        for part in parts[:-1]:
            if part not in current:
                return node
            current = current[part]

        if parts[-1] in current:
            del current[parts[-1]]

        return node

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def get_all(self) -> dict[str, StateNode]:
        """获取所有节点."""
        result: dict[str, StateNode] = {}
        self._collect_all(self._root, "", result)
        return result

    def _collect_all(self, node: Any, prefix: str, result: dict[str, StateNode]) -> None:
        """递归收集所有节点."""
        if isinstance(node, StateNode):
            result[prefix.rstrip(".")] = node
            return

        if isinstance(node, dict):
            for key, child in node.items():
                new_prefix = f"{prefix}{key}." if prefix else f"{key}."
                self._collect_all(child, new_prefix, result)

    def find_by_prefix(self, prefix: str) -> list[StateNode]:
        """根据前缀查找."""
        parts = self._split_key(prefix)
        current = self._root

        for part in parts:
            if part not in current:
                return []
            current = current[part]

        result: dict[str, StateNode] = {}
        self._collect_all(current, prefix + ".", result)
        # 返回节点列表
        return list(result.values())


class StateIndexFactory:
    """状态索引工厂.

    P2 优化：工厂模式创建索引
    """

    _index_types: dict[str, type] = {
        "dict": ThreadSafeDictIndex,
        "hierarchical": HierarchicalIndex,
    }

    @classmethod
    def create_index(cls, index_type: str = "dict") -> StateIndex:
        """创建索引.

        Args:
            index_type: 索引类型

        Returns:
            索引实例

        Raises:
            ValueError: 如果索引类型不存在
        """
        if index_type not in cls._index_types:
            raise ValueError(f"Unknown index type: {index_type}")

        return cls._index_types[index_type]()

    @classmethod
    def register_index_type(cls, name: str, index_class: type) -> None:
        """注册新的索引类型.

        Args:
            name: 类型名称
            index_class: 索引类
        """
        cls._index_types[name] = index_class

    @classmethod
    def get_available_types(cls) -> list[str]:
        """获取可用的索引类型."""
        return list(cls._index_types.keys())


# 导出公共 API
__all__ = [
    "HierarchicalIndex",
    "StateIndex",
    "StateIndexFactory",
    "ThreadSafeDictIndex",
]
