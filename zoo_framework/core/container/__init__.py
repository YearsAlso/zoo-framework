"""按作用域解析共享对象的容器.

对外面：``ScopedContainer``（容器）、``Scope``/``ScopeKind``（作用域句柄）、
``ThreadSafety``（线程安全归属声明）。

框架自身用 ``registry`` 里的 ``process_scoped`` / ``process_instance`` 把内部管理器登记
为进程级共享，取代原先"用装饰器替换类"的 ``@cage``。

设计取舍见 ``openspec/changes/scoped-container/design.md``：本包只做注册 → 按作用域
解析，**不替换类**，因此类型契约（``isinstance``/``issubclass``）保持有效。
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
