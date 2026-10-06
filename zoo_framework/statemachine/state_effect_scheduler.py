from zoo_framework.event.event_channel_manager import EventChannelManager

from .state_node_index_factory import StateNodeIndexFactory


class StateEffectScheduler:
    """状态节点副作用调度器."""

    # TODO: 通过管道管理器
    _event_channel = EventChannelManager().get_channel(__name__)

    # 历史上的类属性 `_response_list: set = set()` 已删（变更 declare-debt-carriers）：
    # 全仓库零读写的死状态，却是一个类级可变共享——扫描登记机制上线后暴露，
    # 与其登记一个死载体不如直接移除。

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
