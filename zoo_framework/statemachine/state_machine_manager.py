import threading
import time
from collections.abc import Callable
from typing import Any

from zoo_framework.core.container import ThreadSafety, process_scoped
from zoo_framework.core.run_identity import RunIdentity
from zoo_framework.statemachine.state_scope import StateScope
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class StateMachineManager:
    """State machine manager."""

    def __init__(self):
        """Initialize the state machine manager."""
        # State scope mapping
        self._state_scope_map: ThreadSafeDict[str, StateScope] = ThreadSafeDict()

        # Whether the local store has been loaded
        self._local_store_loaded = False

        # Local store strategy
        self._local_store_strategy = None

        # Local store interval
        self._local_store_interval = 0

        # 脏作用域记账（add-state-query-index-and-incremental-persistence 原语 3）：
        # 自上次落盘后被修改过的作用域名集合，供增量持久化"只写脏作用域"使用。
        # 集合本身跨用户线程与 Worker 落盘线程共享，故用独立锁保护（该锁不随
        # manager 被 pickle——落盘的始终是 `_state_scope_map`，不是 manager 本身）。
        self._dirty_scopes: set[str] = set()
        self._dirty_lock = threading.Lock()

    def have_loaded(self):
        """Whether it has been loaded."""
        return self._local_store_loaded

    def load_state_machines(self, state_machine: ThreadSafeDict | dict | None = None) -> None:
        """Load the state machines.

        Restore semantics (adjudicated in change fix-state-restore / #72):
        **whole-table replacement**. The only current consume path is loading
        from disk after the process's first resolution (the instance is
        necessarily empty then), where replacement and merge are equivalent;
        an explicit reload on a non-empty state is a deliberate user action.

        Legacy defect (fixed): what got persisted was the `ThreadSafeDict`
        returned by `get_state_machines()`, and it is **not** a `dict`
        subclass - the old guard `isinstance(state_machine, dict)` was always
        false for the framework's own files, the assignment never ran, yet
        `_local_store_loaded` was set true: the state was never restored and
        the "loaded" illusion blocked retries (see
        tests/test_state_restore.py). The guard now dispatches on the real
        type:

        - `ThreadSafeDict`: restored as-is (the framework's own on-disk form)
        - plain `dict`: wrapped into a `ThreadSafeDict`, so the declared type
          is true on every path (compat entry for old files / manual
          injection; storing a plain dict would blow up `has_key()` at runtime)
        - any other non-None argument: rejected with an explicit `TypeError` -
          silent ignoring is the same family of defect as before; the
          `StateMachineWorker` error path falls back to a fresh state and
          leaves an error log

        Args:
            state_machine: the state scope mapping to restore; None means
                nothing to restore, going straight into new state

        Raises:
            TypeError: the argument is neither None nor a dict/ThreadSafeDict
        """
        if state_machine is not None:
            if isinstance(state_machine, ThreadSafeDict):
                self._state_scope_map = state_machine
            elif isinstance(state_machine, dict):
                self._state_scope_map = ThreadSafeDict(state_machine)
            else:
                raise TypeError(
                    f"the state machine argument must be a dict or ThreadSafeDict, got {type(state_machine).__name__}"
                )
        self._local_store_loaded = True
        # 整表替换后内存态即来自磁盘，不再有"待落盘的脏作用域"（原语 3）。
        self.clear_dirty_scopes()

    def _mark_dirty(self, scope: str) -> None:
        """把一个成功写入过的作用域标记为脏（原语 3）。

        Args:
            scope: 作用域名
        """
        with self._dirty_lock:
            self._dirty_scopes.add(scope)

    def get_dirty_scopes(self) -> set[str]:
        """返回自上次落盘后被修改过的作用域名快照（原语 3）。

        Returns:
            脏作用域名集合的副本（调用方改动不影响内部记账）
        """
        with self._dirty_lock:
            return set(self._dirty_scopes)

    def clear_dirty_scopes(self, scopes: set[str] | None = None) -> None:
        """清除脏标记（原语 3）。

        Args:
            scopes: 要清除的作用域名集合；None 表示清空全部
        """
        with self._dirty_lock:
            if scopes is None:
                self._dirty_scopes.clear()
            else:
                self._dirty_scopes.difference_update(scopes)

    def mark_all_dirty(self) -> None:
        """把当前所有作用域标记为脏（原语 3）。

        用于"一次性整体落盘"场景（如增量模式的首次迁移落盘）。
        """
        with self._dirty_lock:
            self._dirty_scopes = set(self._state_scope_map.keys())

    def get_and_create_scope(self, scope: str):
        """Get and create the scope."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)
        return self._state_scope_map[scope]

    def create_scope(self, scope: str):
        """Create the scope.

        索引类型在**运行期**从配置读取（原语 2）：`@params` 在首次导入时冻结值，
        故必须在配置已读之后（此处）读取，而非模块导入期。

        Raises:
            ValueError: `stateMachine:indexType` 配置为未注册的索引类型名
        """
        if self._state_scope_map.has_key(scope):
            return
        # 惰性导入：保证读取发生在 ParamsFactory 读过配置之后（避免冻结默认值）。
        from zoo_framework.params import StateMachineParams

        self._state_scope_map[scope] = StateScope(index_type=StateMachineParams.STATE_INDEX_TYPE)

    def get_scope_identity(self, scope: str) -> RunIdentity | None:
        """Query the owning run identity of a state scope.

        Ownership is determined by the run that **first wrote** the scope
        (see ``StateScope.set_state_node``). Returns None when the scope does
        not exist or has no identified write yet.

        Args:
            scope: the scope name

        Returns:
            The owning ``RunIdentity``; None when unowned
        """
        state_register = self._state_scope_map.get(scope)
        if state_register is None:
            return None
        return state_register.owner_identity

    def get_scope_session(self, scope: str) -> str | None:
        """Query the owning session identity of a state scope; None when unowned."""
        identity = self.get_scope_identity(scope)
        return identity.session_id if identity is not None else None

    def set_state(self, scope: str, key: str, value):
        """Set the value of a state node."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)

        state_register = self._state_scope_map[scope]
        state_register.set_state_node(key, value)
        # 成功写入后记账为脏（原语 3）；写失败会先抛错，不会到此。
        self._mark_dirty(scope)

    def append_state(self, scope: str, key: str, item: Any) -> None:
        """向集合键逐条追加一个元素。

        追加只新增元素、不重写既有元素；scope 不存在时按需创建。目标键不存在
        时以 ``[item]`` 建节点，当前值不是 ``list`` 时抛 ``TypeError``。既有
        ``set_state`` 的整值替换语义不受影响。

        Args:
            scope: 作用域名
            key: 状态键名
            item: 要追加的元素

        Raises:
            TypeError: 目标键当前值不是 ``list``
        """
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)

        state_register: StateScope = self._state_scope_map[scope]
        state_register.append_state_node(key, item)
        # 成功追加后记账为脏（原语 3）；对非 list 追加会先抛 TypeError。
        self._mark_dirty(scope)

    def compare_and_set(
        self, scope: str, key: str, expected_version: int | None, value: Any
    ) -> bool:
        """带"期望版本"的条件写（compare-and-set）。

        仅当目标节点当前版本严格等于 ``expected_version`` 时写入并递增版本。
        版本不匹配（冲突）以返回值 ``False`` 表达，便于调用方重新读取版本后
        重试；作用域或节点不存在、``expected_version`` 为 None 时才抛错。

        Args:
            scope: 作用域名
            key: 状态键名
            expected_version: 期望的当前版本
            value: 期望写入的值

        Returns:
            已写入返回 True；版本不匹配（未写入）返回 False

        Raises:
            KeyError: 作用域或状态节点不存在
            TypeError: ``expected_version`` 为 None
        """
        if self._state_scope_map.get(scope) is None:
            raise KeyError(f"Scope '{scope}' not found")

        state_register: StateScope = self._state_scope_map[scope]
        written = state_register.compare_and_set(key, expected_version, value)
        if written:
            # 仅成功写入才记账为脏（原语 3）：版本不匹配未修改状态。
            self._mark_dirty(scope)
        return written

    def get_state(self, scope: str, key: str) -> Any:
        """Get the state node."""
        if self._state_scope_map.get(scope) is None:
            return None

        state_register = self._state_scope_map[scope]
        node = state_register.get_state_node(key)
        if None is node:
            return None

        return node.get_value()

    def remove_state(self, scope: str, key: str):
        """Remove the state node."""
        if self._state_scope_map.get(scope) is None:
            return None

        # Fetch once and check: the original code first checked
        # `get_state_node(key) is None` and then fetched **again**, but the map
        # is a ThreadSafeDict - the node could be concurrently removed between
        # the two fetches, so there was a real window (where `node.get_value()`
        # would raise AttributeError). Merging into one fetch removes both the
        # window and the type error.
        state_register: StateScope = self._state_scope_map[scope]
        node = state_register.get_state_node(key)
        if node is None:
            return None

        value = node.get_value()
        state_register.remove_state_node(key)
        # 删除也是一次修改，需记账为脏（原语 3）：否则增量模式下"被删除的作用域"
        # 不会落盘同步——删掉顶层节点后 scope 从内存移除，但持久化文件仍在，重启即
        # 复活。标记后增量落盘会清理其文件与 manifest 条目。
        self._mark_dirty(scope)

        # If it is the top node, remove the scope
        if node.is_top():
            self._state_scope_map.pop(scope)

        return value

    def get_state_machines(self):
        """Get the state machines."""
        return self._state_scope_map

    def observe_state(self, scope: str, key: str, effect: Callable):
        """Observe a state node."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)

        state_register: StateScope = self._state_scope_map[scope]
        state_register.observe_state_node(key, effect)

    def unobserve_state(self, scope: str, key: str, effect: Callable):
        """Remove a state node observer - fixes a memory leak.

        Args:
            scope: the scope name
            key: the state key name
            effect: the observer callback

        Raises:
            KeyError: when the scope or the state does not exist
        """
        if self._state_scope_map.get(scope) is None:
            raise KeyError(f"Scope '{scope}' not found")

        state_register: StateScope = self._state_scope_map[scope]
        state_register.unobserve_state_node(key, effect)

    def evict_expired_scopes(self, ttl_seconds: float) -> list[str]:
        """按作用域 TTL 淘汰过期作用域（原语 3）。

        淘汰判据为 ``now - scope.last_modified > ttl_seconds``：时间基准是**墙钟**
        ``time.time()``（故跨进程重启成立），语义取**最后写入**而非最后访问。淘汰
        为**幂等**——对已移除的作用域再次淘汰是 no-op。

        Args:
            ttl_seconds: 作用域存活时间上限（秒）；``None`` / ``0`` / 负值表示不启用
                淘汰（现状默认，不淘汰任何作用域）

        Returns:
            本次被移除的作用域名列表（供调用方按需清理其持久化文件）；无淘汰时为空
        """
        if not ttl_seconds or ttl_seconds <= 0:
            return []

        now = time.time()
        expired: list[str] = []
        for scope in list(self._state_scope_map.keys()):
            scope_obj = self._state_scope_map.get(scope)
            if scope_obj is None:
                continue
            if now - scope_obj.last_modified > ttl_seconds:
                expired.append(scope)

        for scope in expired:
            # 幂等：已被并发移除时跳过（ThreadSafeDict.pop 无默认值，故先判存在）。
            if self._state_scope_map.has_key(scope):
                self._state_scope_map.pop(scope)

        return expired
