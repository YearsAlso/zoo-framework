"""框架自身的进程级共享注册表.

框架内部需要进程级共享的对象（各管理器）经此注册为**进程级作用域**，而不再依赖
``@cage`` 那种"用装饰器替换类"的隐式全局单例。

``@cage`` 的两条罪状是：**替换类**（于是 ``issubclass`` / ``isinstance`` 双双失效）与
**按裸类名做键**（于是两个同名类互相覆盖）。``process_scoped`` 两条都不犯：类仍是真类，
键是模块 + 限定名，且"进程级"是**声明**出来的——可 ``reset()``、可 ``replace()``、
可从容器查到。

与"外部用户自己注册"的差别只是便利：这里封装掉作用域句柄与构造细节，让调用方写一行
装饰器即可，且 ``X()`` 仍返回进程级实例（调用点零改动）。
"""

from collections.abc import Callable
from typing import Any

from .container import ScopedContainer
from .scope import Scope, ScopeKind

# 框架自身的进程级容器。外部用户可以各建各的容器；这个只服务框架内部。
_process_container = ScopedContainer()


def framework_container() -> ScopedContainer:
    """框架自身的进程级容器（供诊断与测试隔离使用）."""
    return _process_container


def register_process_instance(
    cls: type,
    *,
    thread_safety: str,
    factory: Callable[[], Any] | None = None,
    on_release: Callable[[Any], None] | None = None,
) -> str:
    """把 ``cls`` 登记为进程级共享项.

    Args:
        cls: 待登记的类
        thread_safety: 线程安全归属声明，取值见 ``ThreadSafety``；**必填**
        factory: 自定义构造方式；缺省为调用 ``cls()`` 本身
        on_release: 可选的销毁钩子

    Returns:
        注册项标识（模块 + 限定名）
    """
    return _process_container.register(
        cls,
        scope_kind=ScopeKind.PROCESS,
        thread_safety=thread_safety,
        factory=factory,
        on_release=on_release,
    )


def process_instance(cls: type) -> Any:
    """取 ``cls`` 在进程级作用域内的实例."""
    return _process_container.resolve(cls, Scope.process())


def process_scoped(
    *, thread_safety: str, on_release: Callable[[Any], None] | None = None
) -> Callable[[type], type]:
    """类装饰器：类本身不变，但 ``cls()`` 返回进程级作用域内的唯一实例.

    **不替换类**——这是与 ``@cage`` 的分界，因此 ``issubclass(cls, X)`` 与
    ``isinstance(obj, cls)`` 都照常可用。

    三处实现细节，都是被 CPython 的行为逼出来的：

    1. ``__new__`` 返回的既然是 ``cls`` 的实例，``type.__call__`` **仍会对它再调一次
       ``__init__``**。所以 ``__init__`` 被包成幂等的：只有首次才真正执行。否则
       ``StateMachineManager`` 这类有实例状态的类第二次调用就会把状态重置掉。
    2. 容器的构造方式**必须绕过** ``__new__``（用 ``original_new`` 建对象），否则
       "工厂 → ``cls()`` → ``__new__`` → 解析"会递归回容器自身。
    3. 子类**不**继承进程级身份：``subcls is not cls`` 时走正常构造。否则给基类加一次
       装饰器就会把它的所有子类一起变成同一个共享实例。

    Args:
        thread_safety: 线程安全归属声明，取值见 ``ThreadSafety``；**必填**
        on_release: 可选的销毁钩子

    Returns:
        一个不改变类身份的类装饰器
    """

    def decorate(cls: type) -> type:
        # 下面这组操作就是"动态改写类"本身（本模块的立身之本）：先捕获原始的
        # `__new__` / `__init__`，再换成转发版本。静态检查无法为它建模——读 `cls.__init__`
        # 会被判"不健全"，`original_new(cls)` 也落在 typeshed 的重载之外。故用**定向
        # ignore**（各带错误码）并写明原因，而不是退化成 cast 把它盖住：ignore 至少把
        # "这里绕过了检查"摆在明面上。
        original_new = cls.__new__
        original_init = cls.__init__  # type: ignore[misc]

        def _guarded_init(self, *args, **kwargs):
            if getattr(self, "_scoped_ready", False):
                return
            original_init(self, *args, **kwargs)
            self._scoped_ready = True

        def _delegating_new(subcls, *args, **kwargs):
            if subcls is not cls:
                return original_new(subcls, *args, **kwargs)
            return process_instance(cls)

        def _build():
            obj = original_new(cls)  # type: ignore[call-overload]
            _guarded_init(obj)
            return obj

        cls.__init__ = _guarded_init  # type: ignore[misc]
        # 这一行同时受两个工具约束，而它们要求相反：mypy 判直赋值类型不符（typeshed 把
        # `__new__` 标成重载函数），改成 setattr(cls, "__new__", ...) 又会被 ruff 的 B010
        # （不要用 setattr 传常量属性名）拦下。两者无法同时满足，故保留直赋值并加**定向**
        # ignore——这是"可解释的例外"，不是掩盖可修问题：它压制的是两个工具的对立，不是
        # 一处本可修好的不匹配。
        cls.__new__ = staticmethod(_delegating_new)  # type: ignore[assignment]
        register_process_instance(
            cls, thread_safety=thread_safety, factory=_build, on_release=on_release
        )
        return cls

    return decorate
