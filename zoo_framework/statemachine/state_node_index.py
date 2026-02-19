class StateNodeIndex:
    def __init__(self, state_node):
        self.state_node = state_node
        self.state_effect_map = {}
        self.state_effect_set = set()
        self.id = id(self)
