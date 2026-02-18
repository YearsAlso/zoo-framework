"""
state_effect_scheduler - zoo_framework/statemachine/state_effect_scheduler.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.event.event_channel_manager import EventChannelManager

from .state_node_index_factory import StateNodeIndexFactory


class StateEffectScheduler:
    """状态节点副作用调度器."""

    # TODO: 通过管道管理器
    _event_channel = EventChannelManager().get_channel(__name__)

    # 响应列表
    _response_list = set()

    def __init__(self, state_machine):
        self.state_machine = state_machine
        self.state_effect_map = {}
        self.state_effect_index = StateNodeIndexFactory.create_index(self.state_machine)

    def add_state_effect(self, state_effect):
        """添加状态节点副作用
        :param state_effect: 状态节点副作用
        :return:
        """
        if state_effect.state not in self.state_effect_map:
            self.state_effect_map[state_effect.state] = set()
        self.state_effect_map[state_effect.state].add(state_effect)
        self.state_effect_index.add_state_effect(state_effect)

    def remove_state_effect(self, state_effect):
        """移除状态节点副作用
        :param state_effect: 状态节点副作用
        :return:
        """
        if state_effect.state in self.state_effect_map:
            self.state_effect_map[state_effect.state].remove(state_effect)
            self.state_effect_index.remove_state_effect(state_effect)

    def get_state_effect(self, state):
        """获取状态节点副作用
        :param state: 状态节点
        :return:
        """
        return self.state_effect_map.get(state, set())

    def get_state_effect_index(self):
        """获取状态节点副作用索引
        :return:
        """
        return self.state_effect_index

    def execute_state_effect(self, state, *args, **kwargs):
        """执行状态节点副作用
        :param state: 状态节点
        :return:
        """
        state_effect_set = self.get_state_effect(state)
        for state_effect in state_effect_set:
            state_effect.execute(*args, **kwargs)
