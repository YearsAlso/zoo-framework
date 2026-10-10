"""Container that resolves shared objects per scope.

This module is the **correctness** part of DI: registration, per-scope
resolution, type contracts. It deliberately does not do auto-wiring, dependency
graphs, or cycle detection (see design D6) - get correctness right first, add
convenience later.

The key difference from ``@cage`` is **no class replacement**: ``@cage`` swapped
the class for a factory function, which broke ``issubclass`` / ``isinstance``
(verified by test and caused one P0). The container keeps the class identity
intact; singleton semantics come from the **resolution-time cache**, not from
rewriting the class.

Thread safety: the registry and instance tables are guarded by one reentrant
lock, and instance construction happens under **per-registration** fine-grained
locks, therefore
- concurrent resolution of the same item constructs it exactly once (unlike
  check-then-act, which may build two and drop one);
- building one item does not block resolution of other items;
- calling the container again from inside a factory (same thread) does not
  deadlock - the lock is reentrant.
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
    """Wrap a pre-built instance as a factory.

    The pre-built-instance path needs a callable that returns the same object on
    every call; using the instance itself as the factory would *call the
    instance* (unless it happens to be callable). ``__eq__`` compares by value
    identity, so registering the same instance twice is still recognized as an
    equivalent registration.
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
    """Container resolving shared instances per scope.

    Usage::

        container = ScopedContainer()
        container.register(ChannelManager, scope_kind=ScopeKind.PROCESS,
                           thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        manager = container.resolve(ChannelManager, Scope.process())
    """

    def __init__(self):
        """Construct an empty container."""
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
        """Register an item.

        Args:
            target: a class (identity derived from module + qualname) or a
                string (in which case ``name`` must be given)
            scope_kind: scope kind this item belongs to; see ``ScopeKind``
            thread_safety: thread-safety ownership declaration; see
                ``ThreadSafety``. **Required**: the default of None exists only
                so that "forgot to pass it" lands on the domain error below
                instead of a bare signature error; None itself is **not** a
                legal value and is rejected too
            name: explicit registration name, overriding the class-derived one
            factory: custom constructor; defaults to calling ``target`` itself
            instance: a pre-built instance; accepted for the process scope only
                (see below)
            on_release: destroy hook called when the instance is released,
                signature ``(instance) -> None``; fired **exactly once per
                instance** when its scope is released. No reference counting -
                across Workers "who holds, who releases" is ambiguous, and the
                matching entity of "one per session / per device" is scope
                ownership

        Returns:
            The registration id

        Raises:
            ValueError: invalid scope or thread-safety ownership, missing
                required declaration, duplicate registration, or an
                instance/scope combination that contradicts itself
            TypeError: ``target`` is neither a class nor a string
        """
        if scope_kind not in ScopeKind.ALL:
            raise ValueError(
                f"unknown scope kind {scope_kind!r}; expected one of {list(ScopeKind.ALL)}"
            )

        # 线程安全归属必填：隐式默认一个安全假设，正是 @cage 那类缺陷的温床
        if thread_safety is None:
            raise ValueError(
                f"registration {target!r} declares no thread-safety ownership;"
                f"expected one of {list(ThreadSafety.ALL)} (see: {ThreadSafety.DESCRIPTIONS})"
            )
        if thread_safety not in ThreadSafety.ALL:
            raise ValueError(
                f"unknown thread-safety ownership {thread_safety!r}; expected one of {list(ThreadSafety.ALL)}"
            )

        registered_type = self._resolve_registered_type(target, name)
        if name is not None:
            key = name
        else:
            # _resolve_registered_type 对字符串目标要求必须给出 name，故此处 registered_type
            # 必非 None。显式断言把这条不变量变成检查器可见的，也在原地写清了"为何可调用"。
            assert registered_type is not None
            key = qualified_name(registered_type)

        if factory is not None and instance is not None:
            raise ValueError(
                f"cannot register {key!r}: factory and instance are mutually exclusive"
            )

        # 显式声明：三条分支分别给 _Constant / 工厂 / 类，若交给 mypy 从首条分支推断，
        # 变量会被钉成 `_Constant`，后两条反而成了类型错误。
        product: Callable[[], Any]
        if instance is not None:
            # 预先构造的实例只可能是"一个"实例：会话级要的是每会话一个、原型级要的是
            # 每次一个，两者都与单实例相悖。静默共享会串会话，故明确拒绝。
            if scope_kind != ScopeKind.PROCESS:
                raise ValueError(
                    f"registration {key!r} passes a pre-built instance, which is only valid for the process scope;"
                    f"{scope_kind!r} requires per-scope construction"
                )
            product = _Constant(instance)
        elif factory is not None:
            product = factory
        elif registered_type is not None:
            product = registered_type
        else:
            raise ValueError(
                f"cannot register {key!r}: no construction source (neither a class, a factory nor an instance)"
            )

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
                    f"registration {key!r} already exists ({existing!r}) and differs from this one; use replace() to override"
                )
            self._registrations[key] = registration
        return key

    def _resolve_registered_type(self, target: type | str, name: str | None) -> type | None:
        """Determine the registered type from the arguments; a string target requires an explicit name."""
        if isinstance(target, str):
            if not name:
                raise TypeError(f"registering the string {target!r} requires an explicit name")
            return None
        if not isinstance(target, type):
            raise TypeError(f"registration target must be a class or a string, got {target!r}")
        return target

    @staticmethod
    def _same_registration(existing: Registration, candidate: Registration) -> bool:
        """Whether two registrations are equivalent (keeps re-import idempotent, rather than silently rewriting).

        Construction sources are compared with ``==``: classes and functions by
        identity, pre-built instances by value identity via ``_Constant`` -
        two different ``_Constant`` wrappers around the same object are
        equivalent.
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
        """Resolve the instance within the given scope.

        The scope handle is **required**: there is no "process scope if
        omitted" default. A default handle is exactly what would silently break
        session isolation (see design D3).

        Args:
            target: the class given at registration, or its id (string)
            scope: scope handle

        Returns:
            The instance within this scope

        Raises:
            LookupError: the id is not registered
            ValueError: the scope handle does not match the registration's
                scope; or the thread-safety ownership does not permit this
                access (items declared container-serialized MUST be consumed
                via ``exclusive``; single-thread items MUST NOT be consumed
                from any thread other than the bound one)
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
        """Exclusive access: access to this item is serialized inside the ``with`` block.

        For items declared ``ThreadSafety.CONTAINER_SERIALIZED`` - they do not
        lock themselves; the container provides serialization. What is yielded
        is still the **real instance** (not a proxy), so type contracts are
        unaffected.

        The lock is per-registration and reentrant, so re-entering the same item
        inside an instance method does not deadlock.

        Args:
            target: the class given at registration, or its id
            scope: scope handle

        Yields:
            The instance within this scope
        """
        registration = self._require(target)
        with self._exclusion_lock(registration.name):
            yield self._resolve_instance(registration, scope)

    def _resolve_instance(self, registration: Registration, scope: Scope) -> Any:
        """Actual resolution: validate scope compatibility, then hit/build the cache.

        Callers must already have validated the scope handle type and the
        thread-safety ownership.
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
        """Validate the scope handle's type."""
        if not isinstance(scope, Scope):
            raise TypeError(f"scope must be a Scope handle, got {scope!r}")

    def _guard_access(self, registration: Registration) -> None:
        """Admit or refuse this access according to the thread-safety ownership.

        The declaration is not decorative: if an item declared
        "container-serialized" could still be taken away via plain ``resolve``,
        the guarantee would be empty; the same holds for a "single-thread" item
        consumed from any thread.
        """
        if registration.thread_safety == ThreadSafety.CONTAINER_SERIALIZED:
            raise ValueError(
                f"registration {registration.name!r} is declared as"
                f"{ThreadSafety.CONTAINER_SERIALIZED!r} (container-serialized),"
                f"and must be consumed via exclusive(), not resolve()"
            )
        if registration.thread_safety == ThreadSafety.SINGLE_THREAD:
            self._claim_thread(registration)

    # ------------------------------------------------------------------ 释放

    def release(self, scope: Scope) -> list[str]:
        """Release every instance within the scope, firing each registration's destroy hook.

        Only instances **belonging to this handle** are released: releasing a
        session scope does not touch process-scoped items (they are process-wide
        by definition), and releasing a process-scoped handle does not touch
        session-scoped items.

        Idempotent: from the second call on the scope holds no instances, so no
        hooks fire and nothing raises. A hook that raises does not block the
        release of the remaining instances - otherwise one bad hook would leak
        all the others - the exception is logged.

        Args:
            scope: scope handle

        Returns:
            The ids of the instances released this call (cache order)
        """
        self._check_scope_handle(scope)
        subject = scope.cache_key
        if subject is None:
            # 原型级不缓存，没有可释放的实例
            return []
        return self._release_subject(subject)

    def _release_subject(self, subject: tuple) -> list[str]:
        """Release every instance held under a cache subject (process or one session).

        Injected overrides are not included: they are not in the instance table
        and need no lifecycle (see ``replace``).
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
        """Call the destroy hook; failures are logged only and do not interrupt the rest of the release."""
        if hook is None:
            return
        try:
            hook(instance)
        except Exception as e:
            LogUtils.error(
                f"releasing {name!r} raised during its destroy hook and was skipped: {e}",
                ScopedContainer.__name__,
            )

    def _claim_thread(self, registration: Registration) -> None:
        """Bind a "single-thread" registration to the thread that first consumed it.

        Later consumption from other threads MUST NOT silently return the
        instance. The spec allows "refuse or warn loudly"; this implementation
        chooses **refuse**: once the constraint is declared, out-of-bounds use
        should fail on the spot - if an item genuinely needs cross-thread
        sharing it belongs to "instance-guaranteed" or "container-serialized",
        so change the declaration rather than loosen the check.
        """
        current = threading.get_ident()
        with self._lock:
            owner = self._thread_owners.get(registration.name)
            if owner is None:
                self._thread_owners[registration.name] = current
                return
        if owner != current:
            raise ValueError(
                f"registration {registration.name!r} is declared as {ThreadSafety.SINGLE_THREAD!r}"
                f"(single-thread only), bound to thread {owner}; the current thread {current} may not consume it;"
                f"for cross-thread sharing, change the declaration to {ThreadSafety.INSTANCE_GUARANTEED!r} "
                f"or {ThreadSafety.CONTAINER_SERIALIZED!r}"
            )

    # ------------------------------------------------------------------ 内部工具

    def _require(self, target: type | str) -> Registration:
        """Fetch the registration; fail loudly listing known ids if not registered."""
        key = target if isinstance(target, str) else qualified_name(target)
        with self._lock:
            registration = self._registrations.get(key)
            if registration is None:
                known = sorted(self._registrations)
                raise LookupError(f"unknown id {key!r}; registered: {known}")
        return registration

    @staticmethod
    def _check_scope_compatibility(registration: Registration, scope: Scope) -> None:
        """Check that the scope handle is compatible with the registration's scope.

        Process-scoped items can be resolved with any handle (they are unique
        process-wide by definition); session-scoped items MUST be resolved with a
        session handle - resolving one with a process handle means "merging N
        sessions into one", and a prototype handle would mean "do not cache what
        must be cached" - both are silent semantic downgrades.
        """
        if registration.scope_kind != ScopeKind.SESSION:
            return
        if scope.kind != ScopeKind.SESSION:
            raise ValueError(
                f"registration {registration.name!r} is session-scoped and must be resolved with a session scope, got {scope!r}"
            )

    @staticmethod
    def _store_key(registration: Registration, scope: Scope) -> tuple:
        """The cache key for this registration under this handle.

        Process-scoped items always land on the process-level cache regardless
        of which handle was passed in - this is exactly how "a process-scoped
        registration is the same instance across sessions" is implemented.
        """
        if registration.scope_kind == ScopeKind.PROCESS:
            return ("process", registration.name)
        return ("session", scope.session_id, registration.name)

    def _creation_lock(self, store_key: tuple) -> threading.Lock:
        """Get the creation lock for this cache key (creates on demand)."""
        with self._lock:
            lock = self._creation_locks.get(store_key)
            if lock is None:
                lock = threading.Lock()
                self._creation_locks[store_key] = lock
            return lock

    def _exclusion_lock(self, name: str) -> threading.RLock:
        """Get the exclusive-access lock for this registration (creates on demand).

        Per registration, not per cache key: the scope instances under one
        declaration serialize independently of each other.
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
        """Inject an override for this scope (test seam).

        The replaced scope range is **the same** as the resolution scope range:
        override keys share the shape of cache keys, so a process-scoped item is
        replaced at **process** range (it is the one process-wide instance
        anyway) and a session-scoped item is replaced per session - exactly
        "the replacement applies only to the given scope".

        The injection takes effect immediately and drops instances already built
        for that scope. **Destroy hooks do NOT fire**: replacement is a test
        seam, not the end of a lifecycle; run ``release(scope)`` first if hooks
        are needed.

        Args:
            target: the class given at registration, or its id
            scope: scope handle
            factory: replacement constructor
            instance: replacement instance; mutually exclusive with factory

        Raises:
            ValueError: neither factory nor instance given, or both given
            LookupError: the id is not registered
        """
        self._check_scope_handle(scope)
        registration = self._require(target)
        self._check_scope_compatibility(registration, scope)

        if factory is not None and instance is not None:
            raise ValueError(
                f"replacing {registration.name!r}: factory and instance are mutually exclusive"
            )
        # 用 if/elif 而非三元表达式：后者让 mypy 只能看见 `Callable | None`，无法用上面
        # 那处检查把它收窄；显式分支才让它看到"此处必非 None"。
        product: Callable[[], Any]
        if instance is not None:
            product = _Constant(instance)
        elif factory is not None:
            product = factory
        else:
            raise ValueError(f"replacing {registration.name!r} requires a factory or an instance")
        with self._lock:
            self._overrides[self._override_key(registration, scope)] = product
            if registration.scope_kind != ScopeKind.PROTOTYPE:
                # 原型级本就不缓存，没有可丢的实例
                self._instances.pop(self._store_key(registration, scope), None)

    def reset(self) -> list[str]:
        """Reset the container: clear all overrides and release all built instances.

        "Back to initial state" means three things: no overrides, no leftover
        instances, no single-thread bindings. Registrations themselves are
        **kept** - they are the container's configuration, not test-produced
        state.

        Instances go through the same path as ``release``, so declared destroy
        hooks fire as usual and failures are logged only.

        Returns:
            The ids of the released instances (sorted, for easy assertion)
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
        """The override key; same shape as ``_store_key``, so scope semantics match exactly."""
        if registration.scope_kind == ScopeKind.PROCESS:
            return ("process", registration.name)
        if registration.scope_kind == ScopeKind.PROTOTYPE:
            return ("prototype", registration.name)
        return ("session", scope.session_id, registration.name)

    def _override_for(self, registration: Registration, scope: Scope) -> Callable[[], Any] | None:
        """The override for this scope, or None when none was injected."""
        key = self._override_key(registration, scope)
        with self._lock:
            return self._overrides.get(key)

    # ------------------------------------------------------------------ 查询

    def registered(self) -> list[str]:
        """Currently registered ids (sorted)."""
        with self._lock:
            return sorted(self._registrations)

    def live_names(self, scope: Scope) -> list[str]:
        """The ids of instances currently held in this scope (sorted).

        One use is verifying that release actually took effect: it must be empty
        afterwards. Prototype-scoped items are not cached, so this is always
        empty for them.

        Args:
            scope: scope handle

        Returns:
            The registration ids of instances built under this handle
        """
        self._check_scope_handle(scope)
        subject = scope.cache_key
        if subject is None:
            return []
        with self._lock:
            return sorted(key[-1] for key in self._instances if key[: len(subject)] == subject)

    def get_registration(self, target: type | str) -> Registration:
        """Fetch the registration itself (for diagnostics and migration checks).

        Args:
            target: the class given at registration, or its id

        Returns:
            The corresponding ``Registration``
        """
        return self._require(target)
