from __future__ import annotations

import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from zoo_framework.statemachine.state_node_type import StateNodeType
from zoo_framework.utils import LogUtils

# The effect executor: module-level shared, lazily built (align-execution-primitives D2).
# Replaces the historical gevent.spawn/joinall: the write path's synchronous
# wait for effects is **deliberately kept** (non-blocking delivery is a
# separately adjudicated behavior decision); only the primitive changes:
# effects run concurrently, waited at most _EFFECT_JOIN_TIMEOUT_SECONDS
# seconds, and the write returns normally after the timeout.
_EFFECT_JOIN_TIMEOUT_SECONDS = 5
_EFFECT_EXECUTOR_WORKERS = 8

_effect_executor: ThreadPoolExecutor | None = None
_effect_executor_lock = threading.Lock()


def _get_effect_executor() -> ThreadPoolExecutor:
    """Get the shared effect executor (double-checked-lock lazy build).

    Never shut down proactively: reclaimed by concurrent.futures' atexit hook
    at interpreter exit; effects are user callbacks and the framework does
    not force-kill them (the greenlet era did not either).
    """
    global _effect_executor
    if _effect_executor is None:
        with _effect_executor_lock:
            if _effect_executor is None:
                _effect_executor = ThreadPoolExecutor(
                    max_workers=_EFFECT_EXECUTOR_WORKERS,
                    thread_name_prefix="zoo-state-effect",
                )
    return _effect_executor


class StateNode:
    """State node."""

    def __init__(self, key: str, value: Any, effect_list: list[types.FunctionType] | None = None):
        # The annotation used to be `list[StateEffect]`, but what actually goes
        # into the list are **functions** (proven both by add_effect's
        # isinstance(effect, types.FunctionType) and by _perform_effect's
        # executor.submit(effect, ...)); and `StateEffect` has no __call__,
        # so that type could never be executed. Changed to the honest
        # `list[types.FunctionType]`.
        self._effect_list: list[types.FunctionType] = []
        self._version = int(time.time())
        self._is_top = False
        self._parent: Any | None = None
        self._children: list[Any] = []
        self._type = StateNodeType.string

        if effect_list is None:
            effect_list = []
        self._value = value
        self._effect_list = effect_list
        self.key = key

    def set_top(self, is_top: bool) -> None:
        """Set whether it is the root node."""
        self._is_top = is_top

    def is_top(self) -> bool:
        """Whether it is the root node."""
        return self._is_top

    def to_be_top(self) -> None:
        """Mark it as the root node."""
        self._is_top = True

    def get_key(self) -> str:
        """Get the state node key."""
        return self.key

    def add_child(self, child: Any) -> None:
        """Add a child node."""
        if child in self._children or child == self:
            return
        self._children.append(child)

    def get_type(self):
        """Get the state node type."""
        return self._type

    def get_value(self) -> Any:
        """Get the state node value."""
        if len(self._children) == 0:
            return self._value
        return self.get_children_value()

    def get_children_value(self) -> dict:
        """Get the children values."""
        _result: dict = {}
        i = 0
        for child in self._children:
            LogUtils.debug(f"${child.get_key}:{child.get_value()}")
            key = child.get_key
            if key is None:
                continue
            if key in _result:
                i += 1
                _result[f"{key}-{i}"] = child.get_value()
            else:
                _result[child.get_key()] = child.get_value()
        return _result

    def set_key(self, key: str) -> None:
        """Set the state node key."""
        self.key = key
        if self._type is StateNodeType.branch:
            self._update_children_key()

    def _update_children_key(self) -> None:
        """Update the children keys."""
        for i, child in enumerate(self._children):
            child.set_key(f"{self.key}.{i}")

    def set_value(self, value: Any) -> None:
        """Set the state node value."""
        version = int(time.time())
        self._type = StateNodeType.get_type_by_value(value)
        self._value = value
        self._update_version()
        self._perform_effect(value, version)

    def _perform_effect(self, value: Any, version: int) -> None:
        """Perform the state node effects.

        Effects run concurrently on the shared thread executor; the write
        waits synchronously within the timeout. An exception raised by an
        effect does not propagate to the writer but MUST be observable
        (logged).
        """
        if len(self._effect_list) == 0:
            return

        executor = _get_effect_executor()
        futures = [
            executor.submit(effect, {"value": value, "version": version})
            for effect in self._effect_list
        ]
        wait(futures, timeout=_EFFECT_JOIN_TIMEOUT_SECONDS)

        for f in futures:
            if not f.done():
                continue
            # After done(), exception() does not block; like gevent.joinall, it is not re-raised.
            exc = f.exception()
            if exc is not None:
                LogUtils.warning(f"state effect raised an exception: {exc!r}", "StateNode")

    def _update_version(self) -> None:
        """Update the state node version."""
        self.version = int(time.time())

    def get_state(self) -> Any:
        """Get the state node value."""
        return self._value

    def add_effect(self, effect: types.FunctionType | None) -> None:
        """Add an effect to the state node."""
        if effect is None:
            return
        if isinstance(effect, types.FunctionType) and effect not in self._effect_list:
            self._effect_list.append(effect)

    def remove_effect(self, effect: types.FunctionType | None) -> None:
        """Remove an effect from the state node - fixes a memory leak.

        Args:
            effect: the effect function to remove

        Raises:
            ValueError: when the effect is not in the list
        """
        if effect is None:
            return

        try:
            self._effect_list.remove(effect)
            LogUtils.debug(f"✅ Effect removed from state node '{self.key}'")
        except ValueError:
            LogUtils.warning(f"⚠️ Effect not found in state node '{self.key}'")

    def get_children(self) -> list[Any]:
        """Get the children."""
        return self._children
