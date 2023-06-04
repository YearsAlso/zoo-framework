from core.thread_safe_dict import ThreadSafeDict
from zoo_framework.core import cage
from statemachine.state_register import StateRegister


@cage
class StateMachineManager(object):
    _state_register_map = ThreadSafeDict()
    _loaded = False

    def have_loaded(self):
        """
        是否已经加载
        """
        return self._loaded

    def load_state_machines(self, state_machine=None):
        """
        加载状态机
        """
        if state_machine is None:
            state_machine = StateRegister()
        self._state_register_map = state_machine
        self._loaded = True

    def get_and_create_scope(self, scope):
        """
        获取并创建作用域
        """
        if self._state_register_map.get(scope) is None:
            self.create_scope(scope)
        return self._state_register_map[scope]

    def create_scope(self, scope):
        """
        创建作用域
        """
        if self._state_register_map.has_key(scope):
            return
        self._state_register_map[scope] = StateRegister()

    def set_state(self, scope, key, value):
        """
        设置状态节点的值
        """
        if self._state_register_map.get(scope) is None:
            self.create_scope(scope)

        state_register = self._state_register_map[scope]
        state_register[key] = value

    def get_state(self, scope, key):
        """
        获取状态节点
        """
        if self._state_register_map.get(scope) is None:
            return None

        state_register = self._state_register_map[scope]
        return state_register.get(key)

    def remove_state(self, topic):
        """
        移除状态节点
        """
        self._state_register_map[topic] = None

    def get_state_machines(self):
        """
        获取状态机
        """
        return self._state_register_map
