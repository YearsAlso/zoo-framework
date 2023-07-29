from zoo_framework.core.aop import cage
from statemachine.state_node_index import StateNodeIndex


@cage
class StateNodeIndexFactory(object):
    @classmethod
    def create_index(cls, state_node):
        return StateNodeIndex(state_node)
