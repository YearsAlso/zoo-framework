"""Container that resolves shared objects per scope.

The public surface: ``ScopedContainer`` (the container), ``Scope`` /
``ScopeKind`` (scope handles), ``ThreadSafety`` (thread-safety ownership
declaration).

The framework itself uses ``process_scoped`` / ``process_instance`` from
``registry`` to declare its internal managers as process-level shared,
replacing the former class-replacing ``@cage`` decorator.

Design trade-offs in ``openspec/changes/scoped-container/design.md``: this
package only does registration -> per-scope resolution and **never replaces
classes**, so type contracts (``isinstance``/``issubclass``) stay valid.
"""

from .container import ScopedContainer
from .registration import Registration, qualified_name
from .registry import (
    framework_container,
    process_instance,
    process_scoped,
    register_process_instance,
)
from .scope import Scope, ScopeKind
from .thread_safety import ThreadSafety

__all__ = [
    "Registration",
    "Scope",
    "ScopeKind",
    "ScopedContainer",
    "ThreadSafety",
    "framework_container",
    "process_instance",
    "process_scoped",
    "qualified_name",
    "register_process_instance",
]
