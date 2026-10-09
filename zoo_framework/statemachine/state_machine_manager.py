from collections.abc import Callable
from typing import Any

from zoo_framework.core.container import ThreadSafety, process_scoped
from zoo_framework.statemachine.state_scope import StateScope
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class StateMachineManager:
    """状态机管理器."""

    def __init__(self):
        """初始化状态机管理器."""
        # 状态域映射
        self._state_scope_map: ThreadSafeDict[str, StateScope] = ThreadSafeDict()

        # 本地存储是否已经加载
        self._local_store_loaded = False

        # 本地存储策略
        self._local_store_strategy = None

        # 本地存储时间间隔
        self._local_store_interval = 0

    def have_loaded(self):
        """是否已经加载."""
        return self._local_store_loaded

    def load_state_machines(self, state_machine=None):
        """加载状态机.

        恢复语义（变更 fix-state-restore / #72 裁定）：**整表替换**。
        现行唯一消费路径是进程首次解析后从盘载入（当前实例必为空表），替换与
        合并等价；在非空状态上显式重载是使用者的有意动作。

        历史缺陷（已修）：落盘的是 `get_state_machines()` 返回的 `ThreadSafeDict`，
        而它**不是** `dict` 的子类——旧守卫 `isinstance(state_machine, dict)` 对自己
        写出的文件恒假，赋值从不执行，`_local_store_loaded` 却被置真：状态从未恢复，
        "已加载"假象还挡死重试（实测见 tests/test_state_restore.py）。现守卫按真实
        类型分派：

        - `ThreadSafeDict`：原样恢复（本框架自己的落盘形态）
        - 普通 `dict`：包成 `ThreadSafeDict`，使声明类型在每条路径上为真
          （旧文件/手工注入的兼容入口；直接存 dict 会让 `has_key()` 运行期炸掉）
        - 其它非 None 入参：`TypeError` 明确拒绝——静默忽略正是旧缺陷的同族形态；
          `StateMachineWorker` 的异常路径会退回全新状态并留下错误日志

        Args:
            state_machine: 待恢复的状态域映射；None 表示无可恢复内容，直接进入新状态

        Raises:
            TypeError: 入参既不是 None、也不是 dict/ThreadSafeDict
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

    def get_and_create_scope(self, scope: str):
        """获取并创建作用域."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)
        return self._state_scope_map[scope]

    def create_scope(self, scope: str):
        """创建作用域."""
        if self._state_scope_map.has_key(scope):
            return
        self._state_scope_map[scope] = StateScope()

    def get_scope_identity(self, scope: str):
        """查询状态作用域的归属运行标识.

        归属由**首次写入**该作用域的那次运行确定（见 ``StateScope.set_state_node``）。
        作用域不存在、或尚无带标识的写入时返回 None。

        Args:
            scope: 作用域名

        Returns:
            归属的 ``RunIdentity``；无归属时为 None
        """
        state_register = self._state_scope_map.get(scope)
        if state_register is None:
            return None
        return state_register.owner_identity

    def get_scope_session(self, scope: str) -> str | None:
        """查询状态作用域的归属会话标识；无归属时为 None."""
        identity = self.get_scope_identity(scope)
        return identity.session_id if identity is not None else None

    def set_state(self, scope: str, key: str, value):
        """设置状态节点的值."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)

        state_register = self._state_scope_map[scope]
        state_register.set_state_node(key, value)

    def get_state(self, scope: str, key: str) -> Any:
        """获取状态节点."""
        if self._state_scope_map.get(scope) is None:
            return None

        state_register = self._state_scope_map[scope]
        node = state_register.get_state_node(key)
        if None is node:
            return None

        return node.get_value()

    def remove_state(self, scope: str, key: str):
        """移除状态节点."""
        if self._state_scope_map.get(scope) is None:
            return None

        # 取一次并判空：原先先 `get_state_node(key) is None` 判空、随后**再取一次**，
        # 而 map 是 ThreadSafeDict——两次取值之间节点可能已被并发移除，故原本存在一个
        # 真实空窗（届时 `node.get_value()` 会 AttributeError）。合并为一次取值，
        # 同时消掉该窗口与类型错误。
        state_register: StateScope = self._state_scope_map[scope]
        node = state_register.get_state_node(key)
        if node is None:
            return None

        value = node.get_value()
        state_register.remove_state_node(key)

        # 如果是头部节点，移除作用域
        if node.is_top():
            self._state_scope_map.pop(scope)

        return value

    def get_state_machines(self):
        """获取状态机."""
        return self._state_scope_map

    def observe_state(self, scope: str, key: str, effect: Callable):
        """观察状态节点."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)

        state_register: StateScope = self._state_scope_map[scope]
        state_register.observe_state_node(key, effect)

    def unobserve_state(self, scope: str, key: str, effect: Callable):
        """移除状态节点观察者 - 修复内存泄漏.

        Args:
            scope: 作用域名
            key: 状态键名
            effect: 观察者回调函数

        Raises:
            KeyError: 如果作用域或状态不存在
        """
        if self._state_scope_map.get(scope) is None:
            raise KeyError(f"Scope '{scope}' not found")

        state_register: StateScope = self._state_scope_map[scope]
        state_register.unobserve_state_node(key, effect)
