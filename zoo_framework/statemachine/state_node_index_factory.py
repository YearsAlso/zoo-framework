"""
state_node_index_factory - zoo_framework/statemachine/state_node_index_factory.py

模块功能描述:
TODO: 添加模块功能描述


    """StateNodeIndexFactory - 类功能描述

    TODO: 添加类功能详细描述
    """
作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.core.aop import cage
from zoo_framework.statemachine.state_node_index import StateNodeIndex


@cage
class StateNodeIndexFactory:
    @classmethod
    def create_index(cls, state_node):
        return StateNodeIndex(state_node)
