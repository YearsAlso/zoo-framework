"""State node index factory.

P2 optimization: turn index creation into the factory pattern; the index is
an object, supporting several implementations.
"""

from abc import ABC, abstractmethod
from typing import Any

from zoo_framework.statemachine.state_node import StateNode
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


class StateIndex(ABC):
    """State index abstract base class.

    P2 optimization: define the state index interface.
    """

    @abstractmethod
    def get(self, key: str) -> StateNode | None:
        """Get the state node by key."""
        pass

    @abstractmethod
    def set(self, key: str, node: StateNode) -> None:
        """Set the state node."""
        pass

    @abstractmethod
    def remove(self, key: str) -> StateNode | None:
        """Remove the state node."""
        pass

    @abstractmethod
    def has(self, key: str) -> bool:
        """Check whether it exists."""
        pass

    @abstractmethod
    def get_all(self) -> dict[str, StateNode]:
        """Get all nodes."""
        pass

    @abstractmethod
    def find_by_prefix(self, prefix: str) -> list[StateNode]:
        """Find nodes by prefix."""
        pass


class ThreadSafeDictIndex(StateIndex):
    """Thread-safe dict index.

    An index implementation based on ThreadSafeDict.
    """

    def __init__(self):
        self._index: ThreadSafeDict[str, StateNode] = ThreadSafeDict()

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
        """Find nodes by prefix."""
        result: list[StateNode] = []
        for key, node in self._index.items():
            if key.startswith(prefix):
                result.append(node)
        return result


class HierarchicalIndex(StateIndex):
    """Hierarchical index.

    Organizes the index by hierarchy, supporting faster tree lookups.
    """

    def __init__(self):
        self._root: dict = {}
        self._cache: dict[str, StateNode] = {}

    def _split_key(self, key: str) -> list[str]:
        """Split the key."""
        return key.split(".")

    def get(self, key: str) -> StateNode | None:
        # Check the cache first
        if key in self._cache:
            return self._cache[key]

        # Walk the hierarchy
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

        # Build the hierarchy
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

        # Remove from the cache
        if key in self._cache:
            del self._cache[key]

        # Remove from the hierarchy
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
        """Get all nodes."""
        result: dict[str, StateNode] = {}
        self._collect_all(self._root, "", result)
        return result

    def _collect_all(self, node: Any, prefix: str, result: dict[str, StateNode]) -> None:
        """Collect all nodes recursively."""
        if isinstance(node, StateNode):
            result[prefix.rstrip(".")] = node
            return

        if isinstance(node, dict):
            for key, child in node.items():
                new_prefix = f"{prefix}{key}." if prefix else f"{key}."
                self._collect_all(child, new_prefix, result)

    def find_by_prefix(self, prefix: str) -> list[StateNode]:
        """Find by prefix."""
        parts = self._split_key(prefix)
        current = self._root

        for part in parts:
            if part not in current:
                return []
            current = current[part]

        result: dict[str, StateNode] = {}
        self._collect_all(current, prefix + ".", result)
        # Return the node list
        return list(result.values())


class StateIndexFactory:
    """State index factory.

    P2 optimization: create indexes via the factory pattern.
    """

    _index_types: dict[str, type[StateIndex]] = {
        "dict": ThreadSafeDictIndex,
        "hierarchical": HierarchicalIndex,
    }

    @classmethod
    def create_index(cls, index_type: str = "dict") -> StateIndex:
        """Create an index.

        Args:
            index_type: the index type

        Returns:
            An index instance

        Raises:
            ValueError: when the index type does not exist
        """
        if index_type not in cls._index_types:
            raise ValueError(f"Unknown index type: {index_type}")

        return cls._index_types[index_type]()

    @classmethod
    def register_index_type(cls, name: str, index_class: type) -> None:
        """Register a new index type.

        Args:
            name: the type name
            index_class: the index class
        """
        cls._index_types[name] = index_class

    @classmethod
    def get_available_types(cls) -> list[str]:
        """Get the available index types."""
        return list(cls._index_types.keys())


# 导出公共 API
__all__ = [
    "HierarchicalIndex",
    "StateIndex",
    "StateIndexFactory",
    "ThreadSafeDictIndex",
]
