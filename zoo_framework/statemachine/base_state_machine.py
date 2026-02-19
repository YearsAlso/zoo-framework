"""
base_state_machine - zoo_framework/statemachine/base_state_machine.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

class BaseStateMachine(dict):
    """Base class for all state machines."""

    topic = ""

    def __init__(self, topic):
        dict.__init__(self)
        self.topic = topic

    def next(self, topic):
        pass
