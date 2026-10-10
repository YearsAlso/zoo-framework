"""scoped-container 的测试接缝组回归测试（第 4 组）.

对应 openspec/changes/scoped-container/specs/scoped-container/spec.md 的：

- 测试 MUST 能按作用域替换实现

三条 scenario 各有用例：注入假实现后解析返回假实现、替换不影响其他作用域、重置后回到
初始状态。

设计取舍：替换的键与缓存键**同形**，因此"替换的作用域范围"与"解析的作用域范围"是同
一件事——进程级注册项在进程范围内被替换（它本就是全进程唯一的一个实例），会话级注册项
按会话各自替换。替换**不触发销毁钩子**（它是测试接缝，不是生命周期结束）。
"""

import threading

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
    return type(f"Seam_{marker}", (), {})


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
# 1 · 注入假实现后解析返回假实现
# =============================================================================


class TestReplaceInjectsFake:
    """scoped-container: 注入假实现后解析返回假实现."""

    def test_replaced_instance_is_returned(self, container):
        """Scenario: 注入假实现后解析返回假实现."""
        target = _cls("inst")
        scope = Scope.session("s-inst")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        fake = {"fake": True}

        container.replace(target, scope, instance=fake)

        assert container.resolve(target, scope) is fake

    def test_replaced_factory_is_used(self, container):
        target = _cls("fact")
        scope = Scope.process()
        _register(container, target)

        container.replace(target, scope, factory=lambda: "from-factory")

        assert container.resolve(target, scope) == "from-factory"

    def test_replace_takes_effect_over_an_already_resolved_instance(self, container):
        """已解析出真实实例之后再注入，也须立刻生效."""
        target = _cls("late")
        scope = Scope.process()
        _register(container, target)
        real = container.resolve(target, scope)

        fake = object()
        container.replace(target, scope, instance=fake)

        assert container.resolve(target, scope) is fake
        assert container.resolve(target, scope) is not real

    def test_replace_evicts_the_previous_instance_without_running_its_hook(self, container):
        """替换是测试接缝，不是生命周期结束：不触发销毁钩子，但也不再占着该作用域."""
        target = _cls("evict")
        hooks = []
        scope = Scope.process()
        _register(container, target, on_release=hooks.append)
        container.resolve(target, scope)

        container.replace(target, scope, instance=object())

        assert hooks == [], "替换却触发了销毁钩子"
        assert container.live_names(scope) == [], "被替换掉的实例仍占着该作用域"

    def test_replace_does_not_put_the_fake_into_the_lifecycle(self, container):
        """假实现在实例表之外，故释放不会把它当成受管实例去调钩子."""
        target = _cls("outside")
        hooks = []
        scope = Scope.process()
        _register(container, target, on_release=hooks.append)
        container.replace(target, scope, instance=object())

        assert container.release(scope) == []
        assert hooks == []

    def test_prototype_registration_can_be_replaced(self, container):
        """原型级本就不缓存，替换照样生效（且不会因没有缓存键而报错）."""
        target = _cls("proto")
        _register(container, target, scope_kind=ScopeKind.PROTOTYPE)
        fake = object()

        container.replace(target, Scope.prototype(), instance=fake)

        assert container.resolve(target, Scope.prototype()) is fake


# =============================================================================
# 2 · 替换不影响其他作用域
# =============================================================================


class TestReplaceIsScoped:
    """scoped-container: 替换不影响其他作用域."""

    def test_another_session_still_gets_the_original(self, container):
        """Scenario: 替换不影响其他作用域."""
        target = _cls("twoSessions")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        first, second = Scope.session("s-first"), Scope.session("s-second")
        real_second = container.resolve(target, second)

        container.replace(target, first, instance=object())

        assert type(container.resolve(target, second)) is target
        assert container.resolve(target, second) is real_second

    def test_each_session_can_be_replaced_independently(self, container):
        target = _cls("perSession")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        first, second = Scope.session("s-a"), Scope.session("s-b")
        fake_first, fake_second = object(), object()

        container.replace(target, first, instance=fake_first)
        container.replace(target, second, instance=fake_second)

        assert container.resolve(target, first) is fake_first
        assert container.resolve(target, second) is fake_second

    def test_process_registration_is_replaced_process_wide(self, container):
        """进程级注册项只有一个实例，故替换是进程范围的——与它的作用域语义一致."""
        target = _cls("procWide")
        _register(container, target, scope_kind=ScopeKind.PROCESS)
        fake = object()

        container.replace(target, Scope.process(), instance=fake)

        assert container.resolve(target, Scope.session("any")) is fake

    def test_replacing_one_registration_leaves_others_alone(self, container):
        replaced, untouched = _cls("r-one"), _cls("r-two")
        scope = Scope.process()
        _register(container, replaced)
        _register(container, untouched)

        container.replace(replaced, scope, instance=object())

        assert type(container.resolve(untouched, scope)) is untouched

    def test_replace_requires_a_scope_whose_kind_matches(self, container):
        """会话级注册项不能被"进程范围"替换——那等于把 N 个会话合成一个."""
        target = _cls("mismatch")
        _register(container, target, scope_kind=ScopeKind.SESSION)

        with pytest.raises(ValueError):
            container.replace(target, Scope.process(), instance=object())


# =============================================================================
# 3 · 重置后回到初始状态
# =============================================================================


class TestResetRestoresInitialState:
    """scoped-container: 重置后回到初始状态."""

    def test_reset_restores_the_original_implementation(self, container):
        """Scenario: 重置后回到初始状态."""
        target = _cls("resetme")
        scope = Scope.process()
        _register(container, target)

        container.replace(target, scope, instance={"fake": True})
        container.reset()

        resolved = container.resolve(target, scope)
        assert type(resolved) is target
        assert resolved != {"fake": True}

    def test_reset_clears_every_scope_at_once(self, container):
        target = _cls("allScopes")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        first, second = Scope.session("s-1"), Scope.session("s-2")
        container.replace(target, first, instance=object())
        container.replace(target, second, instance=object())

        container.reset()

        assert type(container.resolve(target, first)) is target
        assert type(container.resolve(target, second)) is target

    def test_reset_releases_live_instances_and_runs_hooks(self, container):
        target = _cls("resetLive")
        hooks = []
        scope = Scope.process()
        _register(container, target, on_release=hooks.append)
        container.resolve(target, scope)

        released = container.reset()

        assert released == [qualified_name(target)]
        assert len(hooks) == 1, "reset 未走 release 路径（销毁钩子没触发）"
        assert container.live_names(scope) == []

    def test_reset_keeps_the_registrations(self, container):
        """注册项是容器的配置，不是测试产生的状态，重置后仍应可用."""
        target = _cls("keep")
        _register(container, target)

        container.reset()

        assert container.registered() == [qualified_name(target)]

    def test_reset_is_idempotent_and_empty_when_nothing_to_do(self, container):
        _register(container, _cls("nothing"))

        assert container.reset() == []
        assert container.reset() == []

    def test_reset_clears_single_thread_bindings(self, container):
        """单线程绑定也是测试产生的状态，重置后新线程应可重新绑定."""
        target = _cls("rebind")
        _register(container, target, thread_safety=ThreadSafety.SINGLE_THREAD)
        scope = Scope.process()
        container.resolve(target, scope)  # 绑定到当前线程
        container.reset()

        resolved = []

        def foreign():
            resolved.append(container.resolve(target, scope))

        thread = threading.Thread(target=foreign)
        thread.start()
        thread.join(timeout=5)

        assert len(resolved) == 1, "重置后单线程绑定仍在，新线程被拒"


# =============================================================================
# 4 · 替换与线程安全声明的关系
# =============================================================================


class TestReplaceAndThreadSafety:
    """注入的假实现是测试自己的对象，其线程安全由测试负责，故不受真实实现的声明拦截."""

    def test_serialized_registration_can_be_replaced_and_resolved(self, container):
        target = _cls("serFake")
        _register(container, target, thread_safety=ThreadSafety.CONTAINER_SERIALIZED)
        fake = object()
        container.replace(target, Scope.process(), instance=fake)

        # 真实实现下 resolve 会被拒（须用 exclusive），但假实现不该被这条规则挡住
        assert container.resolve(target, Scope.process()) is fake

    def test_single_thread_registration_can_be_replaced_from_another_thread(self, container):
        target = _cls("oneFake")
        _register(container, target, thread_safety=ThreadSafety.SINGLE_THREAD)
        scope = Scope.process()
        fake = object()
        container.replace(target, scope, instance=fake)

        resolved = []

        def foreign():
            resolved.append(container.resolve(target, scope))

        thread = threading.Thread(target=foreign)
        thread.start()
        thread.join(timeout=5)

        assert resolved == [fake]

    def test_serialized_registration_is_still_usable_through_exclusive_after_replace(
        self, container
    ):
        target = _cls("serExcl")
        _register(container, target, thread_safety=ThreadSafety.CONTAINER_SERIALIZED)
        fake = object()
        container.replace(target, Scope.process(), instance=fake)

        with container.exclusive(target, Scope.process()) as instance:
            assert instance is fake


# =============================================================================
# 5 · 替换入口的参数校验
# =============================================================================


class TestReplaceValidation:
    def test_unregistered_target_is_rejected(self, container):
        with pytest.raises(LookupError):
            container.replace(_cls("ghost"), Scope.process(), instance=object())

    def test_neither_factory_nor_instance_is_rejected(self, container):
        target = _cls("neither")
        _register(container, target)

        with pytest.raises(ValueError) as exc:
            container.replace(target, Scope.process())

        assert "requires a factory or an instance" in str(exc.value)

    def test_both_factory_and_instance_is_rejected(self, container):
        target = _cls("both")
        _register(container, target)

        with pytest.raises(ValueError) as exc:
            container.replace(target, Scope.process(), factory=dict, instance={})

        assert "mutually exclusive" in str(exc.value)

    def test_scope_handle_is_required(self, container):
        target = _cls("noscope")
        _register(container, target)

        with pytest.raises(TypeError):
            container.replace(target, None, instance=object())
