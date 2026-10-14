import copy
import threading
import time
from typing import Any

from zoo_framework.core.run_identity import RunIdentity, current_identity
from zoo_framework.statemachine.state_index_factory import StateIndex, StateIndexFactory
from zoo_framework.statemachine.state_node import StateNode
from zoo_framework.statemachine.state_node_type import StateNodeType
from zoo_framework.utils import LogUtils


class StateScope:
    """State scope - P2 optimized version.

    P2 optimizations:
    1. creates the index via a factory
    2. supports multiple index implementations
    3. supports switching the index type dynamically

    Attributes:
        _state_index: the state-node index
    """

    def __init__(self, index_type: str = "dict"):
        """Initialize the state scope.

        P2 optimization: creates the index via a factory.

        Args:
            index_type: the index type ("dict" or "hierarchical")
        """
        # P2 optimization: create the index via the factory
        self._state_index: StateIndex = StateIndexFactory.create_index(index_type)
        # 变更级可变锁：ThreadSafeDict 只保证单次 get / set 原子，不保证
        # "读取-改-写"整体原子。set_state_node / append_state_node /
        # compare_and_set 的读-改-写段统一持此锁，使版本递增与追加在并发下
        # 良定义（一个 scope 内串行，跨 scope 不互斥）。用 RLock 是因为
        # set_state_node 处理分支值时会递归重入。
        self._mutation_lock = threading.RLock()
        # 最后写入时间戳（墙钟秒，add-state-query-index-and-incremental-persistence
        # 原语 3）：TTL 淘汰按其与墙钟之差判定。取"最后写入"而非"最后访问"——读路径
        # 零改动。随 scope 一起 pickle（TTL 需跨进程重启成立），故不参与 __getstate__
        # 的剔除（只剔不可序列化的变更锁）。
        self.last_modified: float = time.time()
        # Owner identity: the **first** writer becomes the owner and it is never
        # rewritten afterwards (see set_state_node). The full RunIdentity is
        # recorded, not just the session, so the "run identity" is queryable on
        # the state side too.
        self.owner_identity: RunIdentity | None = None

    def __getstate__(self) -> dict:
        """序列化时剔除不可序列化的变更锁。

        ``threading.RLock`` 不可 pickle 也不可 deepcopy，而 scope 的持久化路径
        会对整表做 deepcopy + pickle；锁在还原端按需重建即可，无需随载荷走。
        """
        state = self.__dict__.copy()
        state.pop("_mutation_lock", None)
        return state

    def __setstate__(self, state: dict) -> None:
        """还原状态，并为恢复出的 scope 重建变更锁。

        旧存档（本字段引入前）不含 ``last_modified``，此处按加载时刻补一个，
        避免"缺字段 → 0 → 立即被判过期"（TTL 开启时旧数据被误淘汰）。

        Args:
            state: pickle 还原出的实例 ``__dict__``（不含变更锁）
        """
        self.__dict__.update(state)
        self._mutation_lock = threading.RLock()
        if "last_modified" not in self.__dict__:
            self.last_modified = time.time()

    @property
    def owner_session_id(self) -> str | None:
        """The owner session id; None when unowned."""
        return self.owner_identity.session_id if self.owner_identity is not None else None

    def observe_state_node(self, key: str, effect: Any) -> None:
        """Observe a state node.

        When the key does not exist yet, a placeholder node is created before
        the observer is registered: silently dropping the registration would
        break the primary usage of "declare the observer first, wait for the
        data". The asymmetry with `unobserve_state_node` is deliberate -
        unregistering an observer that never existed usually means the caller
        is wrong and it should surface.

        Args:
            key: the state key name
            effect: the observer callback
        """
        node = self.get_state_node(key)
        if node is None:
            self.register_node(key, None)
            node = self.get_state_node(key)
            if node is None:
                return
        node.add_effect(effect)

    def unobserve_state_node(self, key: str, effect: Any) -> None:
        """Remove a state node observer - fixes a memory leak.

        Args:
            key: the state key name
            effect: the observer callback function

        Raises:
            KeyError: when the state node does not exist
        """
        node = self.get_state_node(key)
        if node is None:
            raise KeyError(f"State node '{key}' not found")
        node.remove_effect(effect)

    def register_top_node(self, key: str, value: Any, effect: list | None = None) -> None:
        """Register a root node.

        Args:
            key: the node key name
            value: the node value
            effect: the side-effect list
        """
        node = StateNode(key, value, effect)
        self._state_index.set(node.get_key(), node)
        node.to_be_top()

    def register_node(self, key: str, value: Any, effect: list | None = None) -> None:
        """Register a state node.

        Args:
            key: the node key name
            value: the node value
            effect: the side-effect list
        """
        if len(key.split(".")) == 1:
            self.register_top_node(key, value, effect)
            return

        node = StateNode(key, value, effect)
        self._state_index.set(node.get_key(), node)

    def set_state_node(self, key: str, value: Any, effect: list | None = None) -> None:
        """Set the value of a state node.

        读-改-写段持 scope 级变更锁，使版本递增在并发下良定义。

        Args:
            key: the node key name
            value: the node value
            effect: the side-effect list
        """
        with self._mutation_lock:
            # 刷新最后写入时间戳（原语 3）：只要进入写路径即视为一次修改。
            self.last_modified = time.time()
            # The owner identity settles at the **first write**: a scope outlives a
            # single run; rewriting the ownership every time would make "whose
            # session state is this" meaningless. Never rewritten afterwards.
            if self.owner_identity is None:
                identity = current_identity()
                if identity is not None:
                    self.owner_identity = identity

            # 1. split the key
            key_queue = key.split(".")

            if len(key_queue) > 1:
                self._check_and_build_tree(key_queue)
            else:
                # Top-level key: the same semantics as the nested-key branch - update
                # when present, register when absent. This used to return directly
                # when the node already existed, skipping set_value, silently
                # dropping repeated writes of a top-level key (and never firing
                # observers).
                node = self.get_state_node(key)
                if node is None:
                    self.register_node(key, value, effect)
                else:
                    node.set_value(value)
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

    def append_state_node(self, key: str, item: Any) -> None:
        """向集合键逐条追加一个元素。

        键不存在时以 ``[item]`` 建节点（复用 ``set_state_node``，一并落定
        owner identity）；已存在则委托 ``StateNode.append_value``。读-改-写段
        持 scope 级变更锁，保证同键并发追加不丢更新。非 ``list`` 值键抛
        ``TypeError`` 且不覆盖原值。

        Args:
            key: 节点键名
            item: 要追加的元素

        Raises:
            TypeError: 目标键当前值不是 ``list``
        """
        with self._mutation_lock:
            node = self.get_state_node(key)
            if node is None:
                self.set_state_node(key, [item])
                return
            node.append_value(item)
            # 刷新最后写入时间戳（原语 3）；追加失败（非 list）已在上一步抛出，不刷新。
            self.last_modified = time.time()

    def compare_and_set(self, key: str, expected_version: int | None, value: Any) -> bool:
        """带"期望版本"的条件写（compare-and-set）。

        在**同一临界区**内读取节点当前版本、与 ``expected_version`` 严格相等
        比较、相等才写入并递增版本。版本不匹配是预期结果而非错误，故以返回值
        表达（便于调用方重新读取版本后重试）。

        Args:
            key: 节点键名
            expected_version: 期望的当前版本，必须与节点当前版本严格相等
            value: 期望写入的值

        Returns:
            已写入返回 True；版本不匹配（未写入）返回 False

        Raises:
            KeyError: 节点不存在
            TypeError: ``expected_version`` 为 None（无可比较版本）
        """
        with self._mutation_lock:
            node = self.get_state_node(key)
            if node is None:
                raise KeyError(f"State node '{key}' not found")
            if expected_version is None:
                raise TypeError("expected_version is required for compare_and_set")
            if node.get_version() != expected_version:
                return False
            node.set_value(value)
            # 仅在写入成功时刷新最后写入时间戳（原语 3）：版本不匹配未修改状态，
            # 不算一次写入。
            self.last_modified = time.time()
            return True

    def update_state_node(self, key: str, node: StateNode) -> None:
        """Update a state node.

        Args:
            key: the node key name
            node: the state node
        """
        self._state_index.set(key, node)

    def _check_children(self, key: str) -> None:
        """Check the children."""
        pass

    def _check_and_build_tree(self, key_queue: list[str]) -> None:
        """Check and build the tree structure.

        Args:
            key_queue: the key queue
        """
        # 2. create the nodes in order
        current_key = key_queue[0]
        for i in range(len(key_queue)):
            if i != 0:
                current_key = f"{current_key}.{key_queue[i]}"
            if self.get_state_node(current_key) is None:
                self.register_node(current_key, None)

        #  3. set up the tree structure
        current_key = key_queue[0]
        for i in range(1, len(key_queue)):
            # [Known defect] The two narrowed annotations below do **not** hold:
            # this path really can produce None (an assert was tried once and the
            # test immediately went red, proving the premise "the loop above has
            # already registered the node" is **not always true**), while the
            # original code passes None to `add_child` - i.e. **hangs a None
            # child node on the tree**; the `current_key` of this loop also never
            # advances. Both belong to this same unresolved semantics question.
            # We deliberately do not guess a fix (changing semantics is someone
            # else's call; recorded in
            # openspec/changes/establish-type-gate/tasks.md 3.1); an anchored
            # ignore keeps the defect visible, not silently altered or deleted.
            node: StateNode = self.get_state_node(current_key)  # type: ignore[assignment]
            children_node: StateNode = self.get_state_node(f"{current_key}.{key_queue[i]}")  # type: ignore[assignment]

            # One key must not be added twice
            node.add_child(children_node)

    def get_state_node(self, key: str) -> StateNode | None:
        """Get a state node.

        Args:
            key: the node key name

        Returns:
            The state node, or None
        """
        return self._state_index.get(key)

    def get_state_value(self, key: str) -> Any:
        """Get a state node's value.

        Args:
            key: the node key name

        Returns:
            The node value
        """
        node = self.get_state_node(key)
        if node is None:
            return None
        return node.get_value()

    def get_state_children_value(self, key: str) -> Any:
        """Get a state node's children values.

        Args:
            key: the node key name

        Returns:
            A dict of child values
        """
        node = self.get_state_node(key)
        if node is None:
            return None
        return node.get_children_value()

    def move_state_node(self, key: str, target_key: str) -> None:
        """Move a state node.

        Args:
            key: the original key name
            target_key: the target key name
        """
        node = self.get_state_node(key)
        if node is None:
            # The arguments used to be swapped: LogUtils.error's signature is
            # (message, cls_name=None), and this passed the **class** as the
            # message and the message as cls_name - the log printed the class
            # object instead of this message.
            LogUtils.error(f"State is not exist, key: {key}", self.__class__.__name__)
            return

        node.set_key(target_key)
        self.set_state_node(target_key, node)
        # Delete the children
        self.remove_state_node(key)

    def remove_state_node(self, key: str) -> None:
        """Remove a state node.

        Args:
            key: the node key name
        """
        node = self.get_state_node(key)
        if node is None:
            # The arguments used to be swapped: LogUtils.error's signature is
            # (message, cls_name=None), and this passed the **class** as the
            # message and the message as cls_name - the log printed the class
            # object instead of this message.
            LogUtils.error(f"State is not exist, key: {key}", self.__class__.__name__)
            return

        if node.get_type() == StateNodeType.branch:
            # A branch node: delete all its children
            for child in node.get_children():
                self.remove_state_node(child.get_key())

        self.set_state_node(key, None)

    def copy_state_node(self, key: str, target_key: Any) -> None:
        """Copy a state node's value.

        Args:
            key: the original key name
            target_key: the target key name
        """
        node = self.get_state_node(key)
        if node is None:
            return
        new_node = copy.deepcopy(node)
        new_node.set_key(target_key)
        self.set_state_node(target_key, new_node)

    def get_all_nodes(self) -> dict:
        """Get all state nodes.

        P2 optimization: supports fetching all nodes.

        Returns:
            A dict of nodes
        """
        return self._state_index.get_all()

    def find_nodes_by_prefix(self, prefix: str) -> list:
        """Find nodes by key prefix.

        P2 optimization: supports prefix lookup.

        Args:
            prefix: the key prefix

        Returns:
            A list of nodes
        """
        return self._state_index.find_by_prefix(prefix)


# Public API exports
__all__ = ["StateScope"]


def get_state_scope(index_type: str = "dict") -> StateScope:
    """Get the global state scope."""
    return StateScope(index_type)
