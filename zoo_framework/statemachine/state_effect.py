"""state_effect - zoo_framework/statemachine/state_effect.py

模块功能描述:
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

class StateEffect:
    """状态节点的副作用."""

    def __init__(self, state, effect):
        self.state = state
        self.effect = effect
        self.execute_count = 0
        self.always_execute = False

        # 响应优先级,添加优先级过滤器，根据执行策略，通过优先级过滤器，测算优先级，并将优先级最高的副作用放入优先级队列
        self.priority = 0

        # 响应次数
        self.response_count = 0

    def get_priority(self):
        return self.priority

    def set_priority(self, priority):
        self.priority = priority

    def get_response_count(self):
        return self.response_count

    def set_response_count(self, response_count):
        self.response_count = response_count

    def __index__(self):
        return self.priority

    def set_always_execute(self, always_execute):
        self.always_execute = always_execute

    def execute(self, *args, **kwargs):
        self.execute_count += 1
        self.effect(*args, **kwargs)
        # 记录执行时的系统时间和负载情况，向调度器报告

    def __repr__(self) -> str:
        """:return: str"""
        return f"StateEffect(state={self.state}, effect={self.effect})"

    def __eq__(self, other) -> bool:
        return self.state == other.state and self.effect == other.effect

    def __hash__(self) -> int:
        return hash((self.state, self.effect))

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)
