"""注册项。

一个注册项记录"如何构造某个类型的实例、它属于哪个作用域、它的线程安全归属是什么"。
标识取**模块 + 限定名**而不是裸类名（见 design D2）：裸类名会让两个同名但定义位置
不同的类互相覆盖，且解析到错的对象时**不报错**。

类型契约由本对象守住：``registered_type`` 始终是注册时提供的那个类，容器既不替换它
也不返回代理对象，因此 ``isinstance`` / ``issubclass`` 照常可用。
"""

from collections.abc import Callable
from typing import Any


def qualified_name(cls: type) -> str:
    """取类型在进程内唯一的标识（模块 + 限定名）.

    Args:
        cls: 待标识的类

    Returns:
        形如 ``pkg.mod.Outer.Inner`` 的标识

    Raises:
        TypeError: 入参不是类
    """
    if not isinstance(cls, type):
        raise TypeError(f"registration id can only be derived from a class, got {cls!r}")
    return f"{cls.__module__}.{cls.__qualname__}"


class Registration:
    """一个注册项.

    Attributes:
        name: 注册项标识（进程内唯一）
        registered_type: 注册时提供的类型；用于类型契约，可为 None（按名注册时）
        scope_kind: 所属作用域种类
        thread_safety: 线程安全归属声明
        explicit_name: 标识是否为显式指定（而非由类推导）
        on_release: 释放该实例时调用的销毁钩子；签名 ``(instance) -> None``
    """

    __slots__ = (
        "explicit_name",
        "factory",
        "name",
        "on_release",
        "registered_type",
        "scope_kind",
        "thread_safety",
    )

    def __init__(
        self,
        name: str,
        registered_type: type | None,
        factory: Callable[[], Any],
        scope_kind: str,
        thread_safety: str,
        explicit_name: bool = False,
        on_release: Callable[[Any], None] | None = None,
    ):
        self.name = name
        self.registered_type = registered_type
        self.factory = factory
        self.scope_kind = scope_kind
        self.thread_safety = thread_safety
        self.explicit_name = explicit_name
        self.on_release = on_release

    def create(self) -> Any:
        """按注册时给出的方式构造一个实例."""
        return self.factory()

    def __repr__(self) -> str:
        return (
            f"Registration(name={self.name!r}, scope={self.scope_kind!r}, "
            f"thread_safety={self.thread_safety!r})"
        )
