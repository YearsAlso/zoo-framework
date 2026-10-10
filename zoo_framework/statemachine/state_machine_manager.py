from collections.abc import Callable
from typing import Any

from zoo_framework.core.container import ThreadSafety, process_scoped
from zoo_framework.statemachine.state_scope import StateScope
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class StateMachineManager:
    """State machine manager."""

    def __init__(self):
        """Initialize the state machine manager."""
        # State scope mapping
        self._state_scope_map: ThreadSafeDict[str, StateScope] = ThreadSafeDict()

        # Whether the local store has been loaded
        self._local_store_loaded = False

        # Local store strategy
        self._local_store_strategy = None

        # Local store interval
        self._local_store_interval = 0

    def have_loaded(self):
        """Whether it has been loaded."""
        return self._local_store_loaded

    def load_state_machines(self, state_machine=None):
        """Load the state machines.

        Restore semantics (adjudicated in change fix-state-restore / #72):
        **whole-table replacement**. The only current consume path is loading
        from disk after the process's first resolution (the instance is
        necessarily empty then), where replacement and merge are equivalent;
        an explicit reload on a non-empty state is a deliberate user action.

        Legacy defect (fixed): what got persisted was the `ThreadSafeDict`
        returned by `get_state_machines()`, and it is **not** a `dict`
        subclass - the old guard `isinstance(state_machine, dict)` was always
        false for the framework's own files, the assignment never ran, yet
        `_local_store_loaded` was set true: the state was never restored and
        the "loaded" illusion blocked retries (see
        tests/test_state_restore.py). The guard now dispatches on the real
        type:

        - `ThreadSafeDict`: restored as-is (the framework's own on-disk form)
        - plain `dict`: wrapped into a `ThreadSafeDict`, so the declared type
          is true on every path (compat entry for old files / manual
          injection; storing a plain dict would blow up `has_key()` at runtime)
        - any other non-None argument: rejected with an explicit `TypeError` -
          silent ignoring is the same family of defect as before; the
          `StateMachineWorker` error path falls back to a fresh state and
          leaves an error log

        Args:
            state_machine: the state scope mapping to restore; None means
                nothing to restore, going straight into new state

        Raises:
            TypeError: the argument is neither None nor a dict/ThreadSafeDict
        """
        if state_machine is not None:
            if isinstance(state_machine, ThreadSafeDict):
                self._state_scope_map = state_machine
            elif isinstance(state_machine, dict):
                self._state_scope_map = ThreadSafeDict(state_machine)
            else:
                raise TypeError(
                    f"the state machine argument must be a dict or ThreadSafeDict, got {type(state_machine).__name__}"
                )
        self._local_store_loaded = True

    def get_and_create_scope(self, scope: str):
        """Get and create the scope."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)
        return self._state_scope_map[scope]

    def create_scope(self, scope: str):
        """Create the scope."""
        if self._state_scope_map.has_key(scope):
            return
        self._state_scope_map[scope] = StateScope()

    def get_scope_identity(self, scope: str):
        """Query the owning run identity of a state scope.

        Ownership is determined by the run that **first wrote** the scope
        (see ``StateScope.set_state_node``). Returns None when the scope does
        not exist or has no identified write yet.

        Args:
            scope: the scope name

        Returns:
            The owning ``RunIdentity``; None when unowned
        """
        state_register = self._state_scope_map.get(scope)
        if state_register is None:
            return None
        return state_register.owner_identity

    def get_scope_session(self, scope: str) -> str | None:
        """Query the owning session identity of a state scope; None when unowned."""
        identity = self.get_scope_identity(scope)
        return identity.session_id if identity is not None else None

    def set_state(self, scope: str, key: str, value):
        """Set the value of a state node."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)

        state_register = self._state_scope_map[scope]
        state_register.set_state_node(key, value)

    def get_state(self, scope: str, key: str) -> Any:
        """Get the state node."""
        if self._state_scope_map.get(scope) is None:
            return None

        state_register = self._state_scope_map[scope]
        node = state_register.get_state_node(key)
        if None is node:
            return None

        return node.get_value()

    def remove_state(self, scope: str, key: str):
        """Remove the state node."""
        if self._state_scope_map.get(scope) is None:
            return None

        # Fetch once and check: the original code first checked
        # `get_state_node(key) is None` and then fetched **again**, but the map
        # is a ThreadSafeDict - the node could be concurrently removed between
        # the two fetches, so there was a real window (where `node.get_value()`
        # would raise AttributeError). Merging into one fetch removes both the
        # window and the type error.
        state_register: StateScope = self._state_scope_map[scope]
        node = state_register.get_state_node(key)
        if node is None:
            return None

        value = node.get_value()
        state_register.remove_state_node(key)

        # If it is the top node, remove the scope
        if node.is_top():
            self._state_scope_map.pop(scope)

        return value

    def get_state_machines(self):
        """Get the state machines."""
        return self._state_scope_map

    def observe_state(self, scope: str, key: str, effect: Callable):
        """Observe a state node."""
        if self._state_scope_map.get(scope) is None:
            self.create_scope(scope)

        state_register: StateScope = self._state_scope_map[scope]
        state_register.observe_state_node(key, effect)

    def unobserve_state(self, scope: str, key: str, effect: Callable):
        """Remove a state node observer - fixes a memory leak.

        Args:
            scope: the scope name
            key: the state key name
            effect: the observer callback

        Raises:
            KeyError: when the scope or the state does not exist
        """
        if self._state_scope_map.get(scope) is None:
            raise KeyError(f"Scope '{scope}' not found")

        state_register: StateScope = self._state_scope_map[scope]
        state_register.unobserve_state_node(key, effect)
