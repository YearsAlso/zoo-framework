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

import contextlib
import threading
from collections.abc import Callable
from typing import Any

from zoo_framework.utils import LogUtils

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
        # "由容器保证串行"的项：按注册项划分的互斥锁；可重入，允许实例方法内再次进入
        self._exclusion_locks: dict[str, threading.RLock] = {}
        # "仅限单线程"的项：首次解析所在线程，作为该注册项的绑定线程
        self._thread_owners: dict[str, int] = {}
        # 测试接缝：按作用域注入的替代实现（见 replace / reset）
        self._overrides: dict[tuple, Callable[[], Any]] = {}

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
        on_release: Callable[[Any], None] | None = None,
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
            on_release: 释放该实例时调用的销毁钩子，签名 ``(instance) -> None``；
                作用域释放时**每个实例只触发一次**。不做引用计数——跨 Worker 时"谁持有
                谁释放"不确定，而"每会话一个/每设备一个"的匹配对象是作用域归属

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
            on_release=on_release,
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
            and existing.on_release is candidate.on_release
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
            ValueError: 作用域句柄与注册项的作用域不相容；或线程安全归属不允许本次取用
                （"由容器保证串行"的项须经 ``exclusive`` 取用；"仅限单线程"的项不得
                被绑定线程以外的线程取用）
        """
        self._check_scope_handle(scope)
        registration = self._require(target)
        self._check_scope_compatibility(registration, scope)
        # 注入了替代实现时跳过归属校验：假实现是测试自己的对象，其线程安全由测试负责，
        # 用真实实现的声明去拦它会挡住合法的注入（见 replace）
        if self._override_for(registration, scope) is None:
            self._guard_access(registration)
        return self._resolve_instance(registration, scope)

    @contextlib.contextmanager
    def exclusive(self, target: type | str, scope: Scope):
        """独占取用：在 ``with`` 块内对该注册项的访问被串行化.

        用于声明为 ``ThreadSafety.CONTAINER_SERIALIZED`` 的项——这类项自身不加锁，
        "串行" 由容器提供。返回的仍是**真实实例**（不是代理），因此类型契约不受影响。

        锁按注册项划分且可重入，故实例方法内部再次进入同一项不会自锁。

        Args:
            target: 注册时给出的类，或其标识
            scope: 作用域句柄

        Yields:
            该作用域内的实例
        """
        registration = self._require(target)
        with self._exclusion_lock(registration.name):
            yield self._resolve_instance(registration, scope)

    def _resolve_instance(self, registration: Registration, scope: Scope) -> Any:
        """实际解析：校验作用域相容性并命中/建立缓存.

        调用方须已完成作用域句柄类型校验与线程安全归属校验。
        """
        self._check_scope_compatibility(registration, scope)

        # 替代实现优先于一切缓存：注入即生效，且不进入本作用域的实例表（它不属于
        # 生命周期管理——没有 on_release 可言，换掉它也不必走 release）
        override = self._override_for(registration, scope)
        if override is not None:
            return override()

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

            # 构造失败时不留下任何痕迹：实例只在成功之后才入缓存，故"半构造实例"不会
            # 被后续解析拿到，也不会在释放时被当成已建立实例处理
            instance = registration.create()

            with self._lock:
                self._instances[store_key] = instance
            return instance

    @staticmethod
    def _check_scope_handle(scope: Any) -> None:
        """校验作用域句柄的类型."""
        if not isinstance(scope, Scope):
            raise TypeError(f"作用域必须是 Scope 句柄，收到 {scope!r}")

    def _guard_access(self, registration: Registration) -> None:
        """按线程安全归属放行或拒绝本次取用.

        声明不是装饰性的：写下"由容器保证串行"却仍能用 ``resolve`` 直接取走实例，
        这条保证就是空的；写下"仅限单线程"却允许任意线程取用，同样是空的。
        """
        if registration.thread_safety == ThreadSafety.CONTAINER_SERIALIZED:
            raise ValueError(
                f"注册项 {registration.name!r} 声明为"
                f"{ThreadSafety.CONTAINER_SERIALIZED!r}（由容器保证串行），"
                f"须经 exclusive() 取用，不得直接 resolve()"
            )
        if registration.thread_safety == ThreadSafety.SINGLE_THREAD:
            self._claim_thread(registration)

    # ------------------------------------------------------------------ 释放

    def release(self, scope: Scope) -> list[str]:
        """释放该作用域内的全部实例，并触发各注册项声明的销毁钩子.

        只释放**属于该句柄**的实例：释放会话作用域不会动进程级项（它本就是全进程共享
        的），释放进程级句柄也不会动会话级项。

        幂等：第二次起该作用域已无实例，既不触发钩子也不抛异常。某个钩子抛异常不会
        阻断其余实例的释放——否则会因一个钩子而泄漏其余实例——该异常被记录。

        Args:
            scope: 作用域句柄

        Returns:
            本次释放的实例标识（按缓存顺序）
        """
        self._check_scope_handle(scope)
        subject = scope.cache_key
        if subject is None:
            # 原型级不缓存，没有可释放的实例
            return []
        return self._release_subject(subject)

    def _release_subject(self, subject: tuple) -> list[str]:
        """释放某个缓存主体（进程级或某个会话）名下的全部实例.

        注入的替代实现不在此列：它不在实例表里，换掉它也不必走生命周期（见 ``replace``）。
        """
        with self._lock:
            victims = [
                (key, instance)
                for key, instance in self._instances.items()
                if key[: len(subject)] == subject
            ]
            # 先摘除再跑钩子：钩子里若再次解析同一项，拿到的是新实例而不是待销毁的那个
            for key, _ in victims:
                del self._instances[key]
            registrations = dict(self._registrations)

        released = []
        for key, instance in victims:
            name = key[-1]
            released.append(name)
            registration = registrations.get(name)
            self._run_release_hook(
                name, registration.on_release if registration is not None else None, instance
            )
        return released

    @staticmethod
    def _run_release_hook(name: str, hook, instance: Any) -> None:
        """调用销毁钩子；失败只记录，不打断其余实例的释放."""
        if hook is None:
            return
        try:
            hook(instance)
        except Exception as e:
            LogUtils.error(
                f"释放 {name!r} 的销毁钩子抛出异常，已跳过: {e}", ScopedContainer.__name__
            )

    def _claim_thread(self, registration: Registration) -> None:
        """把"仅限单线程"的注册项绑定到首次取用它的线程.

        之后从其他线程取用 MUST NOT 静默返回实例。spec 允许"拒绝或显式告警"，本实现
        取**拒绝**：既然声明了这条约束，越界使用就应当当场失败——若某注册项确实需要
        跨线程，那它属于"实例自身保证"或"由容器保证串行"，应当去改声明，而不是放宽检查。
        """
        current = threading.get_ident()
        with self._lock:
            owner = self._thread_owners.get(registration.name)
            if owner is None:
                self._thread_owners[registration.name] = current
                return
        if owner != current:
            raise ValueError(
                f"注册项 {registration.name!r} 声明为 {ThreadSafety.SINGLE_THREAD!r}"
                f"（仅限单线程），其绑定线程为 {owner}，当前线程 {current} 不得取用；"
                f"如需跨线程共享，请改声明为 {ThreadSafety.INSTANCE_GUARANTEED!r} "
                f"或 {ThreadSafety.CONTAINER_SERIALIZED!r}"
            )

    # ------------------------------------------------------------------ 内部工具

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

    def _exclusion_lock(self, name: str) -> threading.RLock:
        """取该注册项的独占访问锁（按需创建）.

        按注册项划分而非按缓存键划分：同一声明下的各个作用域实例各自串行，互不干扰。
        """
        with self._lock:
            lock = self._exclusion_locks.get(name)
            if lock is None:
                lock = threading.RLock()
                self._exclusion_locks[name] = lock
            return lock

    # ------------------------------------------------------------------ 测试接缝

    def replace(
        self,
        target: type | str,
        scope: Scope,
        *,
        factory: Callable[[], Any] | None = None,
        instance: Any = None,
    ) -> None:
        """为该作用域注入替代实现（测试用）.

        替换的作用域范围与解析的作用域范围**同义**：键与缓存键同形，因此进程级注册项
        是在**进程**范围内被替换（它本就是全进程唯一的一个实例），会话级注册项则按会话
        各自替换——这正是"替换仅作用于指定作用域"。

        注入立即生效，并丢掉该作用域已建立的实例。**不触发销毁钩子**：替换是测试接缝，
        不是生命周期的结束；真需要钩子请先 ``release(scope)``。

        Args:
            target: 注册时给出的类，或其标识
            scope: 作用域句柄
            factory: 替代构造函数
            instance: 替代实例；与 factory 只能取其一

        Raises:
            ValueError: 既未给出 factory 也未给出 instance，或两者同时给出
            LookupError: 该标识未注册
        """
        self._check_scope_handle(scope)
        registration = self._require(target)
        self._check_scope_compatibility(registration, scope)

        if factory is not None and instance is not None:
            raise ValueError(
                f"替换 {registration.name!r} 同时给出了 factory 与 instance，二者只能取其一"
            )
        if factory is None and instance is None:
            raise ValueError(f"替换 {registration.name!r} 须给出 factory 或 instance")

        product = _Constant(instance) if instance is not None else factory
        with self._lock:
            self._overrides[self._override_key(registration, scope)] = product
            if registration.scope_kind != ScopeKind.PROTOTYPE:
                # 原型级本就不缓存，没有可丢的实例
                self._instances.pop(self._store_key(registration, scope), None)

    def reset(self) -> list[str]:
        """重置容器：清掉全部替代实现，并释放全部已建立实例.

        "回到初始状态"指三件事：没有假实现、没有遗留下来的实例、没有单线程绑定。注册项
        本身**保留**——它们是容器的配置，不是测试产生的状态。

        实例走的是与 ``release`` 同一条路径，故声明的销毁钩子照常触发、失败也只记录。

        Returns:
            本次释放的实例标识（排序后，便于断言）
        """
        with self._lock:
            self._overrides.clear()
            self._thread_owners.clear()
            subjects = set()
            for key in self._instances:
                # 会话键形如 (session, sid, name)，进程键形如 (process, name)
                subjects.add(key[:2] if key[0] == "session" else key[:1])

        released = []
        for subject in sorted(subjects):
            released.extend(self._release_subject(subject))
        return sorted(released)

    def _override_key(self, registration: Registration, scope: Scope) -> tuple:
        """替代实现的键；与 ``_store_key`` 同形，故作用域语义完全一致."""
        if registration.scope_kind == ScopeKind.PROCESS:
            return ("process", registration.name)
        if registration.scope_kind == ScopeKind.PROTOTYPE:
            return ("prototype", registration.name)
        return ("session", scope.session_id, registration.name)

    def _override_for(self, registration: Registration, scope: Scope) -> Callable[[], Any] | None:
        """取该作用域下的替代实现；没有注入时为 None."""
        key = self._override_key(registration, scope)
        with self._lock:
            return self._overrides.get(key)

    # ------------------------------------------------------------------ 查询

    def registered(self) -> list[str]:
        """当前已注册的标识（排序后）."""
        with self._lock:
            return sorted(self._registrations)

    def live_names(self, scope: Scope) -> list[str]:
        """该作用域当前保有的实例标识（排序后）.

        用途之一是核对释放确实生效：释放后应为空。原型级不缓存，故恒为空。

        Args:
            scope: 作用域句柄

        Returns:
            该句柄下已建立实例的注册项标识
        """
        self._check_scope_handle(scope)
        subject = scope.cache_key
        if subject is None:
            return []
        with self._lock:
            return sorted(key[-1] for key in self._instances if key[: len(subject)] == subject)

    def get_registration(self, target: type | str) -> Registration:
        """取注册项本身（供诊断与迁移期核对）.

        Args:
            target: 注册时给出的类，或其标识

        Returns:
            对应的 ``Registration``
        """
        return self._require(target)
