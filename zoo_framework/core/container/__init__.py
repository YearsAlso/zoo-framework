"""按作用域解析共享对象的容器.

对外面：``ScopedContainer``（容器）、``Scope``/``ScopeKind``（作用域句柄）、
``ThreadSafety``（线程安全归属声明）。

设计取舍见 ``openspec/changes/scoped-container/design.md``：本包只做注册 → 按作用域
解析，**不替换类**，因此类型契约（``isinstance``/``issubclass``）保持有效。
"""

from .container import ScopedContainer
from .registration import Registration, qualified_name
from .scope import Scope, ScopeKind
from .thread_safety import ThreadSafety

__all__ = [
    "Registration",
    "Scope",
    "ScopeKind",
    "ScopedContainer",
    "ThreadSafety",
    "qualified_name",
]
