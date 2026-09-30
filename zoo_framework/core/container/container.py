"""按作用域解析共享对象的容器.

本模块提供 DI 的**正确性**部分：注册、按作用域解析、类型契约。它刻意不做自动装配、
不做依赖图、不做循环依赖检测（见 design D6）——先把正确性做对，便利层后加。

与 ``@cage`` 的关键差别在于**不替换类**：``@cage`` 把类换成工厂函数，于是
``issubclass`` / ``isinstance`` 双双失效（已实测并造成过一次 P0）。容器把"类的身份"
原样保留，单例语义由**解析时的缓存**提供，而不是由改写类的身份提供。

线程安全：容器自身的注册表与实例表由一把可重入锁保护，实例构造在**按注册项划分**
的细粒度锁下进行，因此
- 并发解析同一项只会构造一次（不会像 check-then-act 那样造出两个再丢掉一个）；
- 构造某一项不会阻塞其他项的解析；
- 用户在工厂里再次调用容器（同线程）不会自锁——锁是可重入的。
"""

import threading
from collections.abc import Callable
from typing import Any

from .registration import Registration, qualified_name
from .scope import Scope, ScopeKind
from .thread_safety import ThreadSafety

_MISSING = object()


class _Constant:
    """把既存实例包装成工厂.

    既存实例路径需要的是"每次调用都返回同一个对象"的可调用体；直接把它当工厂用会
    变成"调用该实例"（除非它恰好可调用）。``__eq__`` 按值的同一性比较，使重复登记
    同一实例仍被识别为等价注册。
    """

    __slots__ = ("value",)

    def __init__(self, value: Any):
        self.value = value

    def __call__(self) -> Any:
        return self.value

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, _Constant):
            return NotImplemented
        return self.value is other.value

    def __hash__(self) -> int:
        return id(self.value)

    def __repr__(self) -> str:
        return f"<constant {type(self.value).__name__}>"


class ScopedContainer:
    """按作用域解析共享实例的容器.

    用法::

        container = ScopedContainer()
        container.register(ChannelManager, scope_kind=ScopeKind.PROCESS,
                           thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        manager = container.resolve(ChannelManager, Scope.process())
    """

    def __init__(self):
        """构造一个空容器."""
        # 保护注册表、实例表与细粒度锁表；可重入，允许工厂在同线程内递归解析
        self._lock = threading.RLock()
        self._registrations: dict[str, Registration] = {}
        self._instances: dict[tuple, Any] = {}
        self._creation_locks: dict[tuple, threading.Lock] = {}

    # ------------------------------------------------------------------ 注册

    def register(
        self,
        target: type | str,
        *,
        scope_kind: str,
        thread_safety: str | None = None,
        name: str | None = None,
        factory: Callable[[], Any] | None = None,
        instance: Any = None,
    ) -> str:
        """登记一个注册项.

        Args:
            target: 类（标识由模块 + 限定名推导）或字符串（此时须自行给出 name）
            scope_kind: 所属作用域种类，取值见 ``ScopeKind``
            thread_safety: 线程安全归属声明，取值见 ``ThreadSafety``。**必填**：默认值
                为 None 只是为了让"忘了传"落到下面的领域错误上、而不是抛一个裸
                签名错误；None 本身**不是**合法取值，同样被拒绝
            name: 显式注册名，覆盖由类推导的标识
            factory: 自定义构造函数；缺省为调用 target 本身
            instance: 预先构造好的实例；仅进程级作用域可接受（见下）

        Returns:
            该注册项的标识

        Raises:
            ValueError: 作用域或线程安全归属非法、缺少必需声明、重复注册、
                或 instance 与作用域的组合同义相悖
            TypeError: target 既不是类也不是字符串
        """
        if scope_kind not in ScopeKind.ALL:
            raise ValueError(f"无法识别的作用域 {scope_kind!r}；可选 {list(ScopeKind.ALL)}")

        # 线程安全归属必填：隐式默认一个安全假设，正是 @cage 那类缺陷的温床
        if thread_safety is None:
            raise ValueError(
                f"注册 {target!r} 未声明线程安全归属；"
                f"可选 {list(ThreadSafety.ALL)}（说明：{ThreadSafety.DESCRIPTIONS}）"
            )
        if thread_safety not in ThreadSafety.ALL:
            raise ValueError(
                f"无法识别的线程安全归属 {thread_safety!r}；可选 {list(ThreadSafety.ALL)}"
            )

        registered_type = self._resolve_registered_type(target, name)
        key = name or qualified_name(registered_type)

        if factory is not None and instance is not None:
            raise ValueError(f"注册 {key!r} 同时给出了 factory 与 instance，二者只能取其一")

        if instance is not None:
            # 预先构造的实例只可能是"一个"实例：会话级要的是每会话一个、原型级要的是
            # 每次一个，两者都与单实例相悖。静默共享会串会话，故明确拒绝。
            if scope_kind != ScopeKind.PROCESS:
                raise ValueError(
                    f"注册 {key!r} 提供了既存实例，只能用于进程级作用域；"
                    f"{scope_kind!r} 需要每作用域各自构造"
                )
            product = _Constant(instance)
        elif factory is not None:
            product = factory
        elif registered_type is not None:
            product = registered_type
        else:
            raise ValueError(f"注册 {key!r} 缺少构造方式（既非类，也未给出 factory 或 instance）")

        registration = Registration(
            name=key,
            registered_type=registered_type,
            factory=product,
            scope_kind=scope_kind,
            thread_safety=thread_safety,
            explicit_name=name is not None,
        )

        with self._lock:
            existing = self._registrations.get(key)
            if existing is not None and not self._same_registration(existing, registration):
                raise ValueError(
                    f"注册项 {key!r} 已存在（{existing!r}），与本次注册不同；如需替换请用 replace()"
                )
            self._registrations[key] = registration
        return key

    def _resolve_registered_type(self, target: type | str, name: str | None) -> type | None:
        """由入参确定注册类型；字符串目标必须以显式 name 给出."""
        if isinstance(target, str):
            if not name:
                raise TypeError(f"以字符串 {target!r} 注册时必须同时给出 name")
            return None
        if not isinstance(target, type):
            raise TypeError(f"注册目标只能是类或字符串，收到 {target!r}")
        return target

    @staticmethod
    def _same_registration(existing: Registration, candidate: Registration) -> bool:
        """判断两次注册是否等价（用于让重复导入幂等，而非静默改写）.

        构造方式按 ``==`` 比较：类与函数沿用身份比较，既存实例则由 ``_Constant``
        按值的同一性比较——两个不同的 ``_Constant`` 包着同一个对象即为等价。
        """
        return (
            existing.registered_type is candidate.registered_type
            and existing.factory == candidate.factory
            and existing.scope_kind == candidate.scope_kind
            and existing.thread_safety == candidate.thread_safety
        )

    # ------------------------------------------------------------------ 解析

    def resolve(self, target: type | str, scope: Scope) -> Any:
        """按作用域解析出实例.

        作用域句柄为**必填**：不设"不传即进程级"的默认值。不传句柄的默认值恰恰会让
        会话隔离静默失守（见 design D3）。

        Args:
            target: 注册时给出的类，或其标识（字符串）
            scope: 作用域句柄

        Returns:
            该作用域内的实例

        Raises:
            LookupError: 该标识未注册
            ValueError: 作用域句柄与注册项的作用域不相容
        """
        if not isinstance(scope, Scope):
            raise TypeError(f"作用域必须是 Scope 句柄，收到 {scope!r}")

        registration = self._require(target)
        self._check_scope_compatibility(registration, scope)

        # 原型级不缓存：每次解析都新建，作用域句柄在这里只是"允许解析"的凭据
        if registration.scope_kind == ScopeKind.PROTOTYPE:
            return registration.create()

        store_key = self._store_key(registration, scope)

        with self._lock:
            cached = self._instances.get(store_key, _MISSING)
        if cached is not _MISSING:
            return cached

        # 构造在细粒度锁下进行：不同注册项互不阻塞，同一项只构造一次
        with self._creation_lock(store_key):
            with self._lock:
                cached = self._instances.get(store_key, _MISSING)
            if cached is not _MISSING:
                return cached

            instance = registration.create()

            with self._lock:
                self._instances[store_key] = instance
            return instance

    def _require(self, target: type | str) -> Registration:
        """取出注册项；未注册则明确失败并列出已知标识."""
        key = target if isinstance(target, str) else qualified_name(target)
        with self._lock:
            registration = self._registrations.get(key)
            if registration is None:
                known = sorted(self._registrations)
                raise LookupError(f"未注册的标识 {key!r}；已注册 {known}")
        return registration

    @staticmethod
    def _check_scope_compatibility(registration: Registration, scope: Scope) -> None:
        """校验作用域句柄与注册项的作用域相容.

        进程级项可被任何句柄解析（它本来就是全进程唯一）；会话级项必须由会话句柄解析
        ——用进程句柄解析它意味着"把 N 个会话的实例合成一个"，与原型句柄同理解析则是
        "该缓存的不缓存"，两者都是静默的语义降级。
        """
        if registration.scope_kind != ScopeKind.SESSION:
            return
        if scope.kind != ScopeKind.SESSION:
            raise ValueError(
                f"注册项 {registration.name!r} 是会话级，须由会话作用域解析，收到 {scope!r}"
            )

    @staticmethod
    def _store_key(registration: Registration, scope: Scope) -> tuple:
        """该注册项在该句柄下的缓存键.

        进程级项一律落在进程级缓存上，与传入的是哪种句柄无关——这正是"进程级注册项跨
        会话相同"的实现方式。
        """
        if registration.scope_kind == ScopeKind.PROCESS:
            return ("process", registration.name)
        return ("session", scope.session_id, registration.name)

    def _creation_lock(self, store_key: tuple) -> threading.Lock:
        """取该缓存键的构造锁（按需创建）."""
        with self._lock:
            lock = self._creation_locks.get(store_key)
            if lock is None:
                lock = threading.Lock()
                self._creation_locks[store_key] = lock
            return lock

    # ------------------------------------------------------------------ 查询

    def registered(self) -> list[str]:
        """当前已注册的标识（排序后）."""
        with self._lock:
            return sorted(self._registrations)

    def get_registration(self, target: type | str) -> Registration:
        """取注册项本身（供诊断与迁移期核对）.

        Args:
            target: 注册时给出的类，或其标识

        Returns:
            对应的 ``Registration``
        """
        return self._require(target)
