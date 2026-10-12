from typing import Any

from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.statemachine.state_effect import StateEffect

from .state_node_index import StateNodeIndex
from .state_node_index_factory import StateNodeIndexFactory


class StateEffectScheduler:
    """The state effect scheduler."""

    # TODO: 通过管道管理器
    _event_channel = EventChannelManager().get_channel(__name__)

    # The historical class attribute `_response_list: set = set()` was
    # deleted (declare-debt-carriers): dead state with zero reads or writes
    # repo-wide, yet a class-level mutable shared - exposed once the scan
    # registration mechanism came online; removing it outright was better
    # than registering a dead carrier.

    def __init__(self, state_machine: Any) -> None:
        self.state_machine = state_machine
        self.state_effect_map: dict[object, set[StateEffect]] = {}
        self.state_effect_index: StateNodeIndex = StateNodeIndexFactory.create_index(
            self.state_machine
        )

    def add_state_effect(self, state_effect: StateEffect) -> None:
        """Add a state effect.

        Args:
            state_effect: the state effect
        """
        if state_effect.state not in self.state_effect_map:
            self.state_effect_map[state_effect.state] = set()
        self.state_effect_map[state_effect.state].add(state_effect)
        # StateNodeIndex 目前**没有** add_state_effect —— 本行在运行期会 AttributeError。
        # 这是既有缺陷（该路径当前无调用者，StateEffectScheduler 全仓无构造点），不是本次
        # 注解引入的；这里不掩盖事实，只对"方法确实不存在"逐行 ignore，缺陷另立 issue 跟踪。
        self.state_effect_index.add_state_effect(state_effect)  # type: ignore[attr-defined]

    def remove_state_effect(self, state_effect: StateEffect) -> None:
        """Remove a state effect.

        Args:
            state_effect: the state effect
        """
        if state_effect.state in self.state_effect_map:
            self.state_effect_map[state_effect.state].remove(state_effect)
            # 同 add_state_effect：StateNodeIndex 上并不存在该方法（既有缺陷，另立 issue）。
            self.state_effect_index.remove_state_effect(state_effect)  # type: ignore[attr-defined]

    def get_state_effect(self, state: object) -> set[StateEffect]:
        """Get the state effects for a state.

        Args:
            state: the state node
        """
        return self.state_effect_map.get(state, set())

    def get_state_effect_index(self) -> StateNodeIndex:
        """Get the state effect index.

        Returns:
            the state effect index
        """
        return self.state_effect_index

    def execute_state_effect(self, state: object, *args: Any, **kwargs: Any) -> None:
        """Execute the state effects for a state.

        Args:
            state: the state node
            *args: positional arguments passed to each effect
            **kwargs: keyword arguments passed to each effect
        """
        state_effect_set = self.get_state_effect(state)
        for state_effect in state_effect_set:
            state_effect.execute(*args, **kwargs)
