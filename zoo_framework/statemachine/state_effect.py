from collections.abc import Callable
from typing import Any


class StateEffect:
    """The side effect of a state node."""

    # The parameters MUST be annotated: previously they were bare, making
    # self.state / self.effect Any, and `__eq__`'s `==` with `and` would
    # propagate Any outward - Any returned from a function declared to return
    # bool. The types take the **actual semantics**: state is only compared /
    # printed / hashed (opaque value -> object), effect gets called via
    # `self.effect(*args, **kwargs)` (-> Callable).
    def __init__(self, state: object, effect: Callable[..., Any]) -> None:
        self.state = state
        self.effect = effect
        self.execute_count = 0
        self.always_execute = False

        # Response priority; a priority filter is to be added: per the
        # execution strategy it computes a priority and puts the
        # highest-priority effect into a priority queue
        self.priority = 0

        # Response count
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
        # TODO: report the system time and load at execution to the scheduler

    def __repr__(self) -> str:
        """:return: str"""
        return f"StateEffect(state={self.state}, effect={self.effect})"

    # `other` is annotated as the same class, not `object`: the body reads
    # `other.state` / `other.effect` **unconditionally**, i.e. it already
    # assumes the peer is a StateEffect - the annotation makes that
    # existing assumption checker-visible. It also violates LSP (the
    # parameter of `object.__eq__` is `object`), hence the targeted
    # ignore. The canonical form is `other: object` plus an `isinstance`
    # early return of `NotImplemented`, but that would change comparison
    # semantics for foreign types (AttributeError ->
    # NotImplemented/False), and `__ne__` would need rewriting in sync -
    # a behavior change, left as a separate decision.
    def __eq__(self, other: "StateEffect") -> bool:  # type: ignore[override]
        return self.state == other.state and self.effect == other.effect

    def __hash__(self) -> int:
        return hash((self.state, self.effect))

    def __ne__(self, other: "StateEffect") -> bool:  # type: ignore[override]
        # Same assumption and same LSP deviation as `__eq__` (rationale
        # above); the two MUST change together.
        return not self.__eq__(other)
