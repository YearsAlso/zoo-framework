"""
    """StateNodeIndex - 类功能描述

    TODO: 添加类功能详细描述
    """
state_node_index - zoo_framework/statemachine/state_node_index.py

模块功能描述:
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

class StateNodeIndex:
    def __init__(self, state_node):
        self.state_node = state_node
        self.state_effect_map = {}
        self.state_effect_set = set()
        self.id = id(self)
