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

        【已知缺陷】对本框架自己写出的文件，本方法**实际什么都没加载**：落盘的是
        `get_state_machines()` 返回的 `ThreadSafeDict`（见 state_machine_work.py 的
        `pickle.dump(deepcopy(...))`），而 `ThreadSafeDict` **不是** `dict` 的子类
        （实测 `isinstance(ThreadSafeDict(), dict) is False`），于是下面的守卫恒假、
        赋值从不执行，`_local_store_loaded` 却被置为 True —— 即**状态从未真正恢复**，
        且"已加载"的假象会阻止后续重试。属确定的语义缺陷，但"该合并还是该替换、
        与进程级单例身份如何交互"是未定的语义问题，**故不猜修**（见
        openspec/changes/establish-type-gate/tasks.md 3.1 的记录）。
        此行本身只做类型上的收口：入参若是普通 `dict`，包成 `ThreadSafeDict` 再存，
        使声明类型 `ThreadSafeDict[str, StateScope]` 在**每条路径上都为真**——原先直接
        赋 `dict` 会让后续 `has_key()` 调用在运行期炸掉（`dict` 无此方法）。
        """
        if state_machine is not None and isinstance(state_machine, dict):
            self._state_scope_map = ThreadSafeDict(state_machine)
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
