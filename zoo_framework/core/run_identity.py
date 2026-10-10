"""Run identity: telling "one run" from "one session", and threading both through events, state, and logs.

Two levels of identity:

- the **run identity** ``run_id`` - identifies one logical run, unique per
  run and constant during the run
- the **session identity** ``session_id`` - identifies the session or
  context a run belongs to; one session may contain several runs

Propagation contract (matches design D3 and is the reason this module
exists):

- **Explicit fields are the source of truth**: carriers such as
  ``WorkerResult`` and ``EventNode`` each hold explicit fields, readable and
  filterable by identity without relying on implicit context
- Context variables are only a **convenience read**, and MUST NOT be assumed
  to work across threads automatically - tasks submitted by
  ``ThreadPoolExecutor`` and newly created threads both **fail to inherit**
  the caller's ``ContextVar``. Cross-thread dispatch MUST therefore go
  through :func:`carry_context`, which copies the context explicitly before
  executing.

Relying on context variables without copying would **silently lose** the
identity when dispatching to a worker thread: what arrives is ``None`` or
(worse) a value bound elsewhere, and neither raises.
"""

import contextvars
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any


class RunIdentity:
    """The identity of one run: run identity + session identity."""

    __slots__ = ("run_id", "session_id")

    def __init__(self, run_id: str, session_id: str):
        self.run_id = run_id
        self.session_id = session_id

    def __repr__(self) -> str:
        return f"RunIdentity(run_id={self.run_id!r}, session_id={self.session_id!r})"

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, RunIdentity)
            and self.run_id == other.run_id
            and self.session_id == other.session_id
        )

    def __hash__(self) -> int:
        return hash((self.run_id, self.session_id))

    @classmethod
    def start(cls, session_id: str | None = None) -> "RunIdentity":
        """Generate a fresh run identity.

        Args:
            session_id: the owning session; None also opens a new session

        Returns:
            The new run identity. Several runs of the same session share
            ``session_id`` while their ``run_id`` differ
        """
        return cls(run_id=uuid.uuid4().hex, session_id=session_id or uuid.uuid4().hex)

    @contextmanager
    def bind(self):
        """Bind this identity as the current context, restoring on exit."""
        token = _CURRENT_IDENTITY.set(self)
        try:
            yield self
        finally:
            _CURRENT_IDENTITY.reset(token)


_CURRENT_IDENTITY: contextvars.ContextVar[RunIdentity | None] = contextvars.ContextVar(
    "zoo_run_identity", default=None
)


def current_identity() -> RunIdentity | None:
    """Read the run identity bound to the current context; None when unbound."""
    return _CURRENT_IDENTITY.get()


def current_run_id() -> str | None:
    """The ``run_id`` of the current run identity; None when unbound."""
    identity = current_identity()
    return identity.run_id if identity else None


def current_session_id() -> str | None:
    """The ``session_id`` of the current run identity; None when unbound."""
    identity = current_identity()
    return identity.session_id if identity else None


def carry_context(func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap ``func`` into a callable that executes together with the caller's context.

    Neither newly created threads nor thread-pool tasks inherit the caller's
    ``ContextVar``, so both the executing body and the completion settlement
    in a worker thread MUST run through this wrapper, or the run identity is
    silently lost at dispatch.

    Returns:
        The wrapped callable; every call executes in the context copy
        captured **when the wrapper was created**
    """
    ctx = contextvars.copy_context()

    def _carried(*args: Any, **kwargs: Any) -> Any:
        return ctx.run(func, *args, **kwargs)

    return _carried
