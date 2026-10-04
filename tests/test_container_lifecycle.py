"""scoped-container 的生命周期与线程安全组回归测试（第 3 组）.

对应 openspec/changes/scoped-container/specs/scoped-container/spec.md 的后两条
Requirement：

- 生命周期 MUST 显式且可释放
- 共享实例的线程安全归属 MUST 被显式声明

第 2 组已覆盖"未声明线程安全归属者被拒绝注册"（那是注册 API 定型时自然落下的），
本组覆盖它的另两条行为：容器保证串行的项被真正串行化、仅限单线程的项不被跨线程取用。

设计取舍见 design D4（显式获取 + 显式释放、不做引用计数）与 D5（归属为注册必填声明）。
"""

import contextlib
import threading
import time

import pytest

from zoo_framework.core.container import (
    Scope,
    ScopedContainer,
    ScopeKind,
    ThreadSafety,
    qualified_name,
)


def _cls(marker):
    """构造一个限定名随 marker 变化的类（每次调用都是独立注册项）."""
    return type(f"Lifecycle_{marker}", (), {})


@pytest.fixture
def container():
    return ScopedContainer()


def _register(container, target, **overrides):
    kwargs = {
        "scope_kind": ScopeKind.PROCESS,
        "thread_safety": ThreadSafety.INSTANCE_GUARANTEED,
    }
    kwargs.update(overrides)
    return container.register(target, **kwargs)


# =============================================================================
# 1 · 显式释放与销毁钩子
# =============================================================================


class TestReleaseTriggersDestroyHook:
    """scoped-container: 作用域释放触发销毁钩子."""

    def test_hook_is_called_once_with_the_instance(self, container):
        """Scenario: 作用域释放触发销毁钩子."""
        target = _cls("hook")
        seen = []
        scope = Scope.session("s-hook")
        _register(
            container,
            target,
            scope_kind=ScopeKind.SESSION,
            on_release=seen.append,
        )
        instance = container.resolve(target, scope)

        container.release(scope)

        assert len(seen) == 1, f"钩子被调用 {len(seen)} 次"
        assert seen[0] is instance, "钩子收到的不是被释放的那个实例"

    def test_no_hook_declared_is_fine(self, container):
        target = _cls("nohook")
        scope = Scope.process()
        _register(container, target)
        container.resolve(target, scope)

        assert container.release(scope) == [qualified_name(target)]

    def test_release_reports_what_it_released(self, container):
        first, second = _cls("r1"), _cls("r2")
        scope = Scope.process()
        _register(container, first)
        _register(container, second)
        container.resolve(first, scope)
        container.resolve(second, scope)

        assert sorted(container.release(scope)) == sorted(
            [qualified_name(first), qualified_name(second)]
        )

    def test_second_release_is_safe_and_does_not_rerun_hooks(self, container):
        """Scenario: 重复释放是安全的."""
        target = _cls("idem")
        calls = []
        scope = Scope.session("s-idem")
        _register(container, target, scope_kind=ScopeKind.SESSION, on_release=calls.append)
        container.resolve(target, scope)

        container.release(scope)
        container.release(scope)  # MUST NOT 抛异常

        assert len(calls) == 1, "销毁钩子被重复调用"

    def test_release_of_an_empty_scope_is_a_noop(self, container):
        assert container.release(Scope.session("never-used")) == []

    def test_release_requires_a_scope_handle(self, container):
        with pytest.raises(TypeError):
            container.release(None)

    def test_prototype_release_is_a_noop(self, container):
        """原型级不缓存，故没有可释放的实例（也不该因调用而报错）."""
        target = _cls("proto")
        _register(container, target, scope_kind=ScopeKind.PROTOTYPE)
        container.resolve(target, Scope.prototype())

        assert container.release(Scope.prototype()) == []


class TestReleaseIsScoped:
    """释放只作用于该句柄保有的实例."""

    def test_session_release_does_not_touch_process_items(self, container):
        """进程级项是全进程共享的，释放某个会话不得销毁它."""
        process_item, session_item = _cls("p"), _cls("s")
        _register(container, process_item, scope_kind=ScopeKind.PROCESS)
        _register(container, session_item, scope_kind=ScopeKind.SESSION)
        scope = Scope.session("s-scoped")
        container.resolve(process_item, scope)
        container.resolve(session_item, scope)

        container.release(scope)

        assert container.live_names(Scope.process()) == [qualified_name(process_item)]

    def test_session_release_does_not_touch_other_sessions(self, container):
        target = _cls("other")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        first, second = Scope.session("s-a"), Scope.session("s-b")
        container.resolve(target, first)
        container.resolve(target, second)

        container.release(first)

        assert container.live_names(second) == [qualified_name(target)]

    def test_process_release_does_not_touch_session_items(self, container):
        target = _cls("mixed")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        scope = Scope.session("s-mixed")
        container.resolve(target, scope)

        container.release(Scope.process())

        assert container.live_names(scope) == [qualified_name(target)]

    def test_resolve_after_release_builds_a_fresh_instance(self, container):
        """释放即该作用域这一轮的结束；再次解析得到新实例，而不是被销毁的那个."""
        target = _cls("again")
        scope = Scope.session("s-again")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        first = container.resolve(target, scope)

        container.release(scope)
        second = container.resolve(target, scope)

        assert second is not first


class TestLiveNamesReflectsRelease:
    """scoped-container: 释放后可查询存活实例."""

    def test_live_names_is_empty_after_release(self, container):
        """Scenario: 释放后可查询存活实例."""
        target = _cls("live")
        scope = Scope.session("s-live")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        container.resolve(target, scope)
        assert container.live_names(scope) == [qualified_name(target)]

        container.release(scope)

        assert container.live_names(scope) == []

    def test_live_names_is_empty_before_any_resolve(self, container):
        _register(container, _cls("idle"))
        assert container.live_names(Scope.process()) == []

    def test_live_names_of_prototype_is_always_empty(self, container):
        target = _cls("plive")
        _register(container, target, scope_kind=ScopeKind.PROTOTYPE)
        container.resolve(target, Scope.prototype())

        assert container.live_names(Scope.prototype()) == []

    def test_live_names_requires_a_scope_handle(self, container):
        with pytest.raises(TypeError):
            container.live_names("not-a-scope")


class TestHookFailureDoesNotLeakOthers:
    """某个钩子失败不得阻断其余实例的释放（否则一个坏钩子会泄漏其他实例）."""

    def test_other_instances_are_still_released(self, container):
        bad, good = _cls("bad"), _cls("good")
        released = []
        scope = Scope.process()

        def exploding(_instance):
            raise RuntimeError("钩子失败")

        _register(container, bad, on_release=exploding)
        _register(container, good, on_release=released.append)
        container.resolve(bad, scope)
        good_instance = container.resolve(good, scope)

        result = container.release(scope)  # MUST NOT 抛出钩子的异常

        assert sorted(result) == sorted([qualified_name(bad), qualified_name(good)])
        assert released == [good_instance], "一个钩子失败导致另一个实例未被释放"
        assert container.live_names(scope) == []


# =============================================================================
# 2 · 构造阶段的异常不留半构造实例
# =============================================================================


class TestConstructionFailureLeavesNothingBehind:
    """scoped-container: 构造阶段抛异常后仍被释放."""

    def test_nothing_is_cached_when_construction_raises(self, container):
        """Scenario: 构造阶段抛异常后仍被释放（不留半构造实例）."""
        target = _cls("boom")

        def exploding_factory():
            raise RuntimeError("构造失败")

        _register(container, target, factory=exploding_factory)
        scope = Scope.process()

        with pytest.raises(RuntimeError, match="构造失败"):
            container.resolve(target, scope)

        assert container.live_names(scope) == [], "构造失败却留下了实例"

    def test_a_failed_item_does_not_block_releasing_a_good_one(self, container):
        """某注册项构造失败后，释放作用域仍应正常释放其他已建立的实例."""
        bad, good = _cls("badbuild"), _cls("goodbuild")
        released = []
        scope = Scope.process()
        _register(
            container,
            bad,
            factory=lambda: (_ for _ in ()).throw(RuntimeError("构造失败")),
        )
        _register(container, good, on_release=released.append)
        container.resolve(good, scope)
        with pytest.raises(RuntimeError):
            container.resolve(bad, scope)

        container.release(scope)

        assert len(released) == 1, "构造失败影响了其他实例的释放"

    def test_retry_after_failure_can_succeed(self, container):
        """构造锁不得因异常而残留——否则该注册项此后再无法解析."""
        target = _cls("retry")
        attempts = []

        def flaky_factory():
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("第一次失败")
            return {"built": len(attempts)}

        _register(container, target, factory=flaky_factory)
        scope = Scope.process()

        with pytest.raises(RuntimeError):
            container.resolve(target, scope)

        assert container.resolve(target, scope) == {"built": 2}

    def test_concurrent_failure_does_not_poison_other_threads(self, container):
        """一个线程构造失败，不应让其他线程永久卡住或拿到半成品."""
        target = _cls("racefail")
        calls = []

        def one_shot_factory():
            calls.append(1)
            raise RuntimeError("构造失败")

        _register(container, target, factory=one_shot_factory)
        scope = Scope.process()
        errors = []

        def worker():
            try:
                container.resolve(target, scope)
            except RuntimeError as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert len(errors) == 4
        assert container.live_names(scope) == []


# =============================================================================
# 3 · 线程安全归属：由容器保证串行
# =============================================================================


class TestContainerSerializedIsEnforced:
    """scoped-container: 声明为由容器保证的项被串行访问."""

    def test_resolve_is_refused_and_points_at_exclusive(self, container):
        """声明不是装饰性的：能直接 resolve 走实例，这条保证就是空的."""
        target = _cls("ser")
        _register(container, target, thread_safety=ThreadSafety.CONTAINER_SERIALIZED)

        with pytest.raises(ValueError) as exc:
            container.resolve(target, Scope.process())

        assert "exclusive" in str(exc.value)

    def test_exclusive_yields_the_real_instance(self, container):
        """返回真实实例而非代理，故类型契约不受影响."""
        target = _cls("serinst")
        _register(container, target, thread_safety=ThreadSafety.CONTAINER_SERIALIZED)

        with container.exclusive(target, Scope.process()) as instance:
            assert type(instance) is target
            assert isinstance(instance, target)

    def test_exclusive_is_the_same_instance_as_the_cached_one(self, container):
        target = _cls("sersame")
        _register(container, target, thread_safety=ThreadSafety.CONTAINER_SERIALIZED)
        scope = Scope.process()

        with container.exclusive(target, scope) as first:
            pass
        with container.exclusive(target, scope) as second:
            pass

        assert first is second

    def test_concurrent_exclusive_blocks_do_not_overlap(self, container):
        """Scenario: 声明为由容器保证的项被串行访问.

        用"块内计数恒为 1"判定：任何时刻只有一个线程处于块内即为串行化。
        """
        target = _cls("sercon")
        _register(container, target, thread_safety=ThreadSafety.CONTAINER_SERIALIZED)
        scope = Scope.process()

        inside = []
        overlaps = []
        rounds = 6
        barrier = threading.Barrier(rounds)

        def use(index):
            barrier.wait(timeout=5)
            with container.exclusive(target, scope):
                inside.append(index)
                if len(inside) > 1:
                    overlaps.append(tuple(inside))
                time.sleep(0.02)
                inside.remove(index)

        threads = [threading.Thread(target=use, args=(i,)) for i in range(rounds)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert not overlaps, f"出现并发进入：{overlaps}"

    def test_exclusive_is_reentrant_on_one_thread(self, container):
        """实例方法内部再次独占同一项不得自锁."""
        target = _cls("serreent")
        _register(container, target, thread_safety=ThreadSafety.CONTAINER_SERIALIZED)
        scope = Scope.process()

        # 两层同时进入，验证同一线程上可重入（换成不可重入的锁会在此死锁）
        with (
            container.exclusive(target, scope) as outer,
            container.exclusive(target, scope) as inner,
        ):
            assert inner is outer

    def test_exclusive_works_for_other_declarations_too(self, container):
        """对未声明串行的项也可以独占取用——那是更严的取用方式，不是矛盾."""
        target = _cls("serextra")
        _register(container, target, thread_safety=ThreadSafety.INSTANCE_GUARANTEED)

        with container.exclusive(target, Scope.process()) as instance:
            assert type(instance) is target

    def test_serialized_item_can_still_be_released(self, container):
        """独占访问的项同样归作用域所有，释放要生效."""
        target = _cls("serrel")
        released = []
        _register(
            container,
            target,
            thread_safety=ThreadSafety.CONTAINER_SERIALIZED,
            on_release=released.append,
        )
        scope = Scope.process()
        with container.exclusive(target, scope):
            pass

        container.release(scope)

        assert len(released) == 1
        assert container.live_names(scope) == []


# =============================================================================
# 4 · 线程安全归属：仅限单线程
# =============================================================================


class TestSingleThreadIsEnforced:
    """scoped-container: 声明为非线程安全的项不被跨线程使用."""

    def test_the_claiming_thread_can_resolve(self, container):
        target = _cls("one")
        _register(container, target, thread_safety=ThreadSafety.SINGLE_THREAD)

        assert type(container.resolve(target, Scope.process())) is target

    def test_another_thread_is_refused_not_silently_served(self, container):
        """Scenario: 声明为非线程安全的项不被跨线程使用.

        spec 允许"拒绝或显式告警"，本实现取拒绝——MUST NOT 静默返回实例。
        """
        target = _cls("onecross")
        _register(container, target, thread_safety=ThreadSafety.SINGLE_THREAD)
        scope = Scope.process()
        container.resolve(target, scope)  # 绑定到当前（主）线程

        outcome = []

        def foreign():
            try:
                container.resolve(target, scope)
                outcome.append(("returned", None))
            except ValueError as e:
                outcome.append(("refused", str(e)))

        thread = threading.Thread(target=foreign)
        thread.start()
        thread.join(timeout=5)

        assert outcome, "外部线程没有返回结果"
        kind, message = outcome[0]
        assert kind == "refused", "跨线程取用被静默放行"
        assert "仅限单线程" in message
        assert ThreadSafety.INSTANCE_GUARANTEED in message
        assert ThreadSafety.CONTAINER_SERIALIZED in message

    def test_refusal_happens_without_building_an_instance(self, container):
        """拒绝须发生在构造之前，否则白造一个实例出来."""
        target = _cls("onebuild")
        built = []
        _register(
            container,
            target,
            factory=lambda: (built.append(1), object())[1],
            thread_safety=ThreadSafety.SINGLE_THREAD,
        )
        scope = Scope.process()
        container.resolve(target, scope)
        assert len(built) == 1

        def foreign():
            with contextlib.suppress(ValueError):
                container.resolve(target, scope)

        thread = threading.Thread(target=foreign)
        thread.start()
        thread.join(timeout=5)

        assert len(built) == 1, "被拒绝的取用仍然构造了实例"

    def test_instance_guaranteed_items_are_not_restricted(self, container):
        """对照组：声明为实例自身保证的项可以跨线程取用."""
        target = _cls("crossfree")
        _register(container, target, thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        scope = Scope.process()
        first = container.resolve(target, scope)

        resolved = []

        def foreign():
            resolved.append(container.resolve(target, scope))

        thread = threading.Thread(target=foreign)
        thread.start()
        thread.join(timeout=5)

        assert resolved == [first], "实例自身保证的项被错误地限制了跨线程取用"

    def test_binding_is_per_registration_not_global(self, container):
        """一个项被绑定到主线程，不影响另一项在自己的线程里被取用."""
        process_wide, thread_bound = _cls("pw"), _cls("tb")
        _register(container, process_wide, thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        _register(container, thread_bound, thread_safety=ThreadSafety.SINGLE_THREAD)
        scope = Scope.process()
        container.resolve(thread_bound, scope)  # 绑定到主线程

        resolved = []

        def foreign():
            resolved.append(container.resolve(process_wide, scope))

        thread = threading.Thread(target=foreign)
        thread.start()
        thread.join(timeout=5)

        assert len(resolved) == 1
