from zoo_framework.core import cage
from zoo_framework.statemachine.base_state_machine import BaseStateMachine


@cage
class StateMachineManager(object):
    _state_machines = {}
    _loaded = False

    def __init__(self):
        pass

    def have_loaded(self):
        return self._loaded

    def load_state_machines(self, state_machine=None):
        if state_machine is None:
            state_machine = {}
        self._state_machines = state_machine
        self._loaded = True

    def create_topic(self, topic):
        if self._state_machines.has_key(topic):
            return
        self._state_machines[topic] = BaseStateMachine(topic)

    def set_topic_value(self, topic, key, value):
        if self._state_machines.get(topic) is None:
            self.create_topic(topic)

        state_machine = self._state_machines[topic]
        state_machine[key] = value

    def get_topic_value(self, topic, key):
        if self._state_machines.get(topic) is None:
            return None

        state_machine = self._state_machines[topic]
        return state_machine.get(key)

    def remove_topic(self, topic):
        self._state_machines[topic] = None

    def get_state_machines(self):
        return self._state_machines
