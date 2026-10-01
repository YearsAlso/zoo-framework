from collections.abc import Callable
from typing import Any


class StateEffect:
    """状态节点的副作用."""

    # 形参必须标注：它们此前是裸的，于是 self.state / self.effect 都成了 Any，而 `__eq__`
    # 的 `==` 与 `and` 会把 Any 一路传出去 → 从声明返回 bool 的函数里返回 Any。
    # 类型取**真实语义**：state 只被比较/打印/哈希（不透明值 → object），
    # effect 会被 `self.effect(*args, **kwargs)` 调用（→ Callable）。
    def __init__(self, state: object, effect: Callable[..., Any]) -> None:
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

    # `other` 标注为同类而非 `object`：函数体**无条件**读 `other.state` / `other.effect`，
    # 即它本就假定对方是 StateEffect —— 标注把这个既有假定写成检查器可见的。它同时违反 LSP
    # （`object.__eq__` 的形参是 `object`），故带定向 ignore。规范写法是 `other: object` +
    # `isinstance` 早返回 `NotImplemented`，但那会改变对外来类型的比较语义（AttributeError →
    # NotImplemented/False），且 `__ne__` 须同步改写 —— 属行为变动，留作独立决定。
    def __eq__(self, other: "StateEffect") -> bool:  # type: ignore[override]
        return self.state == other.state and self.effect == other.effect

    def __hash__(self) -> int:
        return hash((self.state, self.effect))

    def __ne__(self, other: "StateEffect") -> bool:  # type: ignore[override]
        # 与 `__eq__` 同一处假定、同一处 LSP 偏差（理由见上）；两者必须同改。
        return not self.__eq__(other)
