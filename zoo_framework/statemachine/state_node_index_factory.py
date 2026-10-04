from zoo_framework.core.container import ThreadSafety, process_scoped
from zoo_framework.statemachine.state_node_index import StateNodeIndex


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class StateNodeIndexFactory:
    @classmethod
    def create_index(cls, state_node):
        return StateNodeIndex(state_node)
