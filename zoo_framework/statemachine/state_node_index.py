"""状态节点索引：按状态维护 effect 的记账副本。

历史缺陷（issue #208）：``StateEffectScheduler`` 自建立起就调用
``add_state_effect`` / ``remove_state_effect``，但本类并未实现这两个方法——该路径
一旦被构造即 ``AttributeError``（此前无构造点，属死代码上的潜伏缺陷）。本类初始就
带有 ``state_effect_map`` / ``state_effect_set`` 两个空容器却无配套方法，二者当时都是
死状态；本次补齐接口，使其成为真正生效的记账结构。
"""

from typing import Any


class StateNodeIndex:
    """状态节点索引。

    Attributes:
        state_node: 关联的状态节点
        state_effect_map: 状态 -> 该状态下的 effect 集合
        state_effect_set: 全部已登记 effect 的合集
        id: 索引实例标识
    """

    def __init__(self, state_node):
        self.state_node = state_node
        self.state_effect_map: dict[Any, set[Any]] = {}
        self.state_effect_set: set[Any] = set()
        self.id = id(self)

    def add_state_effect(self, state_effect: Any) -> None:
        """登记一个状态 effect：按状态入分组，同时并入全集。

        Args:
            state_effect: 待登记的状态 effect；以 ``state_effect.state`` 为分组键。
        """
        self.state_effect_map.setdefault(state_effect.state, set()).add(state_effect)
        self.state_effect_set.add(state_effect)

    def remove_state_effect(self, state_effect: Any) -> None:
        """移除一个状态 effect：同时从分组与全集中移除。

        幂等：目标不存在时不抛错——索引是调度器记账的**副本**，重复移除不应让调用方的
        簿记路径中断。

        Args:
            state_effect: 待移除的状态 effect。
        """
        bucket = self.state_effect_map.get(state_effect.state)
        if bucket is not None:
            bucket.discard(state_effect)
            if not bucket:
                del self.state_effect_map[state_effect.state]
        self.state_effect_set.discard(state_effect)
