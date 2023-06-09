from typing import Any

from zoo_framework.core.thread_safe_dict import ThreadSafeDict
from zoo_framework.core import cage
from zoo_framework.statemachine.state_register import StateRegister


@cage
class StateMachineManager(object):
    """
    状态机管理器
    """
    def __init__(self):
        """
        初始化状态机管理器
        """
        self._state_register_map = ThreadSafeDict()

        # 本地存储是否已经加载
        self._local_store_loaded = False

        # 本地存储策略
        self._local_store_strategy = None

        # 本地存储时间间隔
        self._local_store_interval = 0

    def have_loaded(self):
        """
        是否已经加载
        """
        return self._local_store_loaded

    def load_state_machines(self, state_machine=None):
        """
        加载状态机
        """
        if state_machine is None:
            state_machine = StateRegister()
        self._state_register_map = state_machine
        self._local_store_loaded = True

    def get_and_create_scope(self, scope: str):
        """
        获取并创建作用域
        """
        if self._state_register_map.get(scope) is None:
            self.create_scope(scope)
        return self._state_register_map[scope]

    def create_scope(self, scope: str):
        """
        创建作用域
        """
        if self._state_register_map.has_key(scope):
            return
        self._state_register_map[scope] = StateRegister()

    def set_state(self, scope: str, key: str, value):
        """
        设置状态节点的值
        """
        if self._state_register_map.get(scope) is None:
            self.create_scope(scope)

        state_register = self._state_register_map[scope]
        state_register.set_state_node(key, value)

    def get_state(self, scope: str, key: str) -> Any:
        """
        获取状态节点
        """
        if self._state_register_map.get(scope) is None:
            return None

        state_register = self._state_register_map[scope]
        node = state_register.get_state_node(key)
        if None is node:
            return None

        return node.get_value()

    def remove_state(self, scope: str, key: str):
        """
        移除状态节点
        """
        if self._state_register_map.get(scope) is None:
            return None

        if self._state_register_map[scope].get_state_node(key) is None:
            return None

        # 移除状态节点
        state_register: StateRegister = self._state_register_map[scope]
        node = state_register.get_state_node(key)

        value = node.get_value()
        state_register.remove_state_node(key)

        # 如果是头部节点，移除作用域
        if node.is_top():
            self._state_register_map.pop(scope)

        return value

    def get_state_machines(self):
        """
        获取状态机
        """
        return self._state_register_map

    def observe_state(self, scope: str, key: str, effect: callable):
        """
        观察状态节点
        """
        if self._state_register_map.get(scope) is None:
            self.create_scope(scope)

        state_register: StateRegister = self._state_register_map[scope]
        state_register.observe_state_node(key, effect)
