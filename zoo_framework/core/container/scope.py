"""Scope expression.

A scope is the boundary of "reusing the same object across Workers": within
the same scope the same registration resolves to the same instance, across
scopes to different instances. It is needed because a **process-level global
singleton** is wrong in multi-session scenarios - two users' agents would
share one tool client (cross-session data), two devices would share one
connection handle (writing the wrong device).

A scope is expressed as an **explicit handle** (see design D3). The caller
passes the handle in and MUST NOT read it implicitly from context variables:
tasks submitted by `ThreadPoolExecutor` do not inherit the caller's context
variables, and when an implicit read falls through, the consequence is not a
"lost identity" but **silently getting another session's object**.

Three scopes:

- process-level: unique in the whole process, the same instance even across
  sessions
- session-level: one per session; the session boundary is carried by the
  session identity of ``core/run_identity``
- prototype-level: a fresh build on every resolution, not cached
"""

from typing import Any

PROCESS_SCOPE_KEY = ("process",)


class ScopeKind:
    """Scope kinds."""

    PROCESS = "process"
    SESSION = "session"
    PROTOTYPE = "prototype"

    ALL = (PROCESS, SESSION, PROTOTYPE)


class Scope:
    """Scope handle.

    The handle is an immutable identity, safe to pass across threads; it
    does **not** carry the instance cache - the cache belongs to the
    container.

    Attributes:
        kind: the scope kind, see ``ScopeKind`` for values
        session_id: the session identity; carried only by a session scope,
            None otherwise
    """

    __slots__ = ("kind", "session_id")

    def __init__(self, kind: str, session_id: str | None = None):
        """Construct a scope handle.

        Args:
            kind: the scope kind
            session_id: the session identity; only a session scope needs it

        Raises:
            ValueError: the kind is unrecognized, or the session identity
                does not match the kind (missing or extra)
        """
        if kind not in ScopeKind.ALL:
            raise ValueError(f"unknown scope kind {kind!r}; expected one of {list(ScopeKind.ALL)}")

        # Without a session id, a session scope cannot tell sessions apart and
        # the cache would degenerate to process level - a silent semantic
        # downgrade, so reject it here rather than fill in a default identity
        if kind == ScopeKind.SESSION and not session_id:
            raise ValueError("a session scope requires a session id")

        # A non-session scope carrying a session id means the caller believed
        # it was isolating when it was not; reject that explicitly too
        if kind != ScopeKind.SESSION and session_id is not None:
            raise ValueError(f"a {kind} scope does not accept a session id, got {session_id!r}")

        self.kind = kind
        self.session_id = session_id

    @classmethod
    def process(cls) -> "Scope":
        """The process-level scope handle."""
        return cls(ScopeKind.PROCESS)

    @classmethod
    def session(cls, session_id: str) -> "Scope":
        """The session-level scope handle.

        Args:
            session_id: the session identity, usually taken from
                ``RunIdentity.session_id``
        """
        return cls(ScopeKind.SESSION, session_id)

    @classmethod
    def prototype(cls) -> "Scope":
        """The prototype-level scope handle (a fresh build per resolution)."""
        return cls(ScopeKind.PROTOTYPE)

    @classmethod
    def of(cls, identity: Any) -> "Scope":
        """Derive a session scope from a run identity.

        This is an **explicit** call: the handle is still passed into the
        container by the caller; it only saves the manual extraction of
        ``session_id``. When the identity is None it is rejected explicitly,
        not falling back to the process level - that would silently merge two
        sessions into one.

        Args:
            identity: a ``RunIdentity`` instance

        Raises:
            ValueError: the identity is None or carries no session identity
        """
        if identity is None:
            raise ValueError(
                "no run identity: cannot derive a session scope (MUST NOT silently fall back to the process scope)"
            )
        session_id = getattr(identity, "session_id", None)
        if not session_id:
            raise ValueError(
                f"run identity {identity!r} carries no session id: cannot derive a session scope"
            )
        return cls.session(session_id)

    @property
    def cache_key(self) -> tuple | None:
        """The cache subject of the scope; a prototype scope does not cache and returns None."""
        if self.kind == ScopeKind.PROTOTYPE:
            return None
        if self.kind == ScopeKind.PROCESS:
            return PROCESS_SCOPE_KEY
        return ("session", self.session_id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Scope):
            return NotImplemented
        return (self.kind, self.session_id) == (other.kind, other.session_id)

    def __hash__(self) -> int:
        return hash((self.kind, self.session_id))

    def __repr__(self) -> str:
        if self.kind == ScopeKind.SESSION:
            return f"Scope(session={self.session_id!r})"
        return f"Scope({self.kind})"
