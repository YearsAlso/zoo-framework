from zoo_framework.core.aop import cage
from zoo_framework.statemachine.state_node_index import StateNodeIndex


@cage
class StateNodeIndexFactory:
    @classmethod
    def create_index(cls, state_node):
        return StateNodeIndex(state_node)
