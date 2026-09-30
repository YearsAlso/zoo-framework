"""scoped-container 的容器／作用域／标识组回归测试（第 2 组）.

对应 openspec/changes/scoped-container/specs/scoped-container/spec.md 的前三条
Requirement：

- 解析 MUST 以作用域为界
- 注册项标识 MUST 在进程内唯一且不依赖类名
- 解析 MUST 保留类型契约

`@cage` 的三处硬伤（同名串号、类型契约被摧毁、无作用域表达）是本组要消灭的对象；
第 5 组迁移使用点后 `@cage` 的语义会改变，故此处不引用它，全部断言针对容器本身。

生命周期的用例在第 3 组，测试替换与重置的用例在第 4 组。
"""

import pytest

from zoo_framework.core.container import (
    Scope,
    ScopedContainer,
    ScopeKind,
    ThreadSafety,
    qualified_name,
)


def _service(marker):
    """构造一个限定名随 marker 变化的实现类.

    标识取"模块 + 限定名"，因此**同名**的类会被识别为同一个注册项。本 helper 把
    marker 编进类名，使每次调用都是一个独立的注册项——用例里要断言同名类被区分开
    时请改用 ``_define_alpha`` / ``_define_beta``。
    """
    return type(f"Service_{marker}", (), {"MARKER": marker})


def _define_alpha():
    """在独立作用域内定义一个名为 SameNameService 的类.

    限定名含所在函数，故与 ``_define_beta`` 里的同名类属于**不同定义位置**——
    这正是"同名但定义位置不同的类 MUST 被识别为不同注册项"要检验的形态。
    """

    class SameNameService:
        MARKER = "alpha"

    return SameNameService


def _define_beta():
    """同上，另一处定义位置."""

    class SameNameService:
        MARKER = "beta"

    return SameNameService


@pytest.fixture
def container():
    return ScopedContainer()


def _register(container, target, **overrides):
    """按最常见的方式登记一项，供本组用例复用."""
    kwargs = {
        "scope_kind": ScopeKind.PROCESS,
        "thread_safety": ThreadSafety.INSTANCE_GUARANTEED,
    }
    kwargs.update(overrides)
    return container.register(target, **kwargs)


# =============================================================================
# 1 · 解析以作用域为界
# =============================================================================


class TestResolutionIsBoundedByScope:
    """scoped-container: 解析 MUST 以作用域为界."""

    def test_same_scope_returns_same_instance(self, container):
        """Scenario: 同一作用域内返回同一实例."""
        target = _service("a")
        _register(container, target)
        scope = Scope.process()

        assert container.resolve(target, scope) is container.resolve(target, scope)

    def test_different_session_scopes_return_different_instances(self, container):
        """Scenario: 不同作用域返回不同实例."""
        target = _service("b")
        _register(container, target, scope_kind=ScopeKind.SESSION)

        first = container.resolve(target, Scope.session("session-1"))
        second = container.resolve(target, Scope.session("session-2"))

        assert first is not second, "两个会话作用域解析到了同一实例"

    def test_process_scoped_item_is_same_across_sessions(self, container):
        """Scenario: 进程级注册项跨会话相同."""
        target = _service("c")
        _register(container, target, scope_kind=ScopeKind.PROCESS)

        first = container.resolve(target, Scope.session("session-1"))
        second = container.resolve(target, Scope.session("session-2"))

        assert first is second, "进程级注册项在不同会话里不是同一实例"

    def test_session_scoped_item_repeats_within_one_session(self, container):
        """同一会话内重复解析仍是同一实例（作用域隔离不推翻幂等）."""
        target = _service("d")
        _register(container, target, scope_kind=ScopeKind.SESSION)
        scope = Scope.session("session-1")

        assert container.resolve(target, scope) is container.resolve(target, scope)

    def test_prototype_scope_yields_a_new_instance_each_time(self, container):
        target = _service("e")
        _register(container, target, scope_kind=ScopeKind.PROTOTYPE)

        assert container.resolve(target, Scope.prototype()) is not container.resolve(
            target, Scope.prototype()
        )

    def test_session_registration_is_not_resolvable_by_process_scope(self, container):
        """用进程句柄解析会话级项意味着把 N 个会话合成一个——须明确拒绝."""
        target = _service("f")
        _register(container, target, scope_kind=ScopeKind.SESSION)

        with pytest.raises(ValueError) as exc:
            container.resolve(target, Scope.process())

        assert "会话级" in str(exc.value)

    def test_resolve_requires_a_scope_handle(self, container):
        """作用域句柄为必填，MUST NOT 有不传即进程级的默认值."""
        _register(container, _service("g"))

        with pytest.raises(TypeError):
            container.resolve(_service("g"), None)

    def test_session_scope_requires_a_session_id(self):
        with pytest.raises(ValueError):
            Scope(ScopeKind.SESSION)

    def test_non_session_scope_rejects_a_session_id(self):
        """非会话句柄带会话标识，说明调用方以为在隔离而实际没有——明确拒绝."""
        with pytest.raises(ValueError):
            Scope(ScopeKind.PROCESS, "session-1")

    def test_scope_of_derives_from_a_run_identity(self):
        """会话句柄可显式地由运行标识派生；无标识时明确失败而非退回进程级."""
        from zoo_framework.core.run_identity import RunIdentity

        identity = RunIdentity.start(session_id="session-of-run")
        assert Scope.of(identity) == Scope.session("session-of-run")

        with pytest.raises(ValueError):
            Scope.of(None)


# =============================================================================
# 2 · 注册项标识在进程内唯一且不依赖类名
# =============================================================================


class TestRegistrationIdentity:
    """scoped-container: 注册项标识 MUST 在进程内唯一且不依赖类名."""

    def test_same_name_classes_are_distinct_registrations(self, container):
        """Scenario: 同名类被区分为不同注册项.

        这正是 `@cage` 的硬伤：它以裸类名做键，两个同名类互相覆盖。
        """
        alpha, beta = _define_alpha(), _define_beta()
        assert alpha.__name__ == beta.__name__ == "SameNameService"

        first_key = _register(container, alpha)
        second_key = _register(container, beta)

        assert first_key != second_key, "同名类被识别为同一个注册项"
        assert sorted(container.registered()) == sorted([first_key, second_key])

    def test_same_name_classes_resolve_to_their_own_type(self, container):
        """Scenario: 同名类的解析各自返回自己的实例."""
        alpha, beta = _define_alpha(), _define_beta()
        _register(container, alpha)
        _register(container, beta)
        scope = Scope.process()

        resolved_alpha = container.resolve(alpha, scope)
        resolved_beta = container.resolve(beta, scope)

        assert type(resolved_alpha) is alpha
        assert type(resolved_beta) is beta
        assert resolved_beta is not resolved_alpha, "第二个解析到了第一个的实例"

    def test_explicit_name_distinguishes_same_name_items(self, container):
        """Scenario: 显式注册名可用于区分同名项."""
        alpha, beta = _define_alpha(), _define_beta()
        _register(container, alpha, name="alpha")
        _register(container, beta, name="beta")
        scope = Scope.process()

        assert type(container.resolve("alpha", scope)) is alpha
        assert type(container.resolve("beta", scope)) is beta

    def test_default_key_is_the_qualified_name(self, container):
        target = _define_alpha()
        assert _register(container, target) == qualified_name(target)
        assert target.__module__ in qualified_name(target)
        assert "SameNameService" in qualified_name(target)

    def test_qualified_name_requires_a_class(self):
        with pytest.raises(TypeError):
            qualified_name("not-a-class")

    def test_identical_reregistration_is_idempotent(self, container):
        """同一项被重复登记（如模块被重新导入）不应报错，也不应改写."""
        target = _service("h")
        first = _register(container, target)
        second = _register(container, target)

        assert first == second
        assert len(container.registered()) == 1

    def test_conflicting_reregistration_is_rejected(self, container):
        """同一标识以不同身份再次登记 MUST 明确失败，MUST NOT 静默覆盖."""
        target = _service("i")
        _register(container, target, thread_safety=ThreadSafety.INSTANCE_GUARANTEED)

        with pytest.raises(ValueError) as exc:
            _register(container, target, thread_safety=ThreadSafety.CONTAINER_SERIALIZED)

        assert "replace" in str(exc.value)

    def test_unregistered_lookup_lists_known_identifiers(self, container):
        """未注册即明确失败，且指出已知标识——MUST NOT 静默造一个实例出来."""
        known = _register(container, _service("j"))

        with pytest.raises(LookupError) as exc:
            container.resolve(_service("k"), Scope.process())

        assert known in str(exc.value), "拒绝信息未列出已注册的标识"


# =============================================================================
# 3 · 解析保留类型契约
# =============================================================================


class TestTypeContractIsPreserved:
    """scoped-container: 解析 MUST 保留类型契约.

    `@cage` 实测输出：``type(Service).__name__ == 'function'``、
    ``issubclass(Service, object)`` → TypeError、``isinstance(a, Service)`` → TypeError。
    本组断言这四件事在容器下都正常。
    """

    def test_resolved_instance_supports_isinstance(self, container):
        """Scenario: 解析结果可用于 isinstance 判定."""
        target = _service("l")
        _register(container, target)

        resolved = container.resolve(target, Scope.process())

        assert isinstance(resolved, target) is True
        assert isinstance(resolved, str) is False

    def test_registered_type_supports_issubclass(self, container):
        """Scenario: 注册类型可用于 issubclass 判定."""
        target = _service("m")
        _register(container, target)

        assert issubclass(target, object) is True

    def test_resolved_type_is_the_registered_type(self, container):
        """Scenario: 解析结果的类型与注册类型一致."""
        target = _service("n")
        _register(container, target)

        assert type(container.resolve(target, Scope.process())) is target

    def test_registration_does_not_replace_the_class(self, container):
        """登记不得改动类本身的身份——这是与 @cage 的分界."""
        target = _service("o")
        before = type(target).__name__

        _register(container, target)

        assert isinstance(target, type)
        assert type(target).__name__ == before


# =============================================================================
# 4 · 线程安全归属必填
# =============================================================================


class TestThreadSafetyDeclarationIsRequired:
    """scoped-container: 线程安全归属 MUST 被显式声明."""

    def test_missing_declaration_is_rejected(self, container):
        """Scenario: 未声明线程安全归属者被拒绝注册."""
        with pytest.raises(ValueError) as exc:
            container.register(_service("p"), scope_kind=ScopeKind.PROCESS)

        assert "线程安全归属" in str(exc.value)

    def test_explicit_none_is_not_accepted_as_a_declaration(self, container):
        """显式传 None 与"忘了传"同罪：MUST NOT 用隐式默认值代替声明."""
        with pytest.raises(ValueError):
            container.register(_service("q"), scope_kind=ScopeKind.PROCESS, thread_safety=None)

    def test_unknown_declaration_is_rejected(self, container):
        with pytest.raises(ValueError) as exc:
            container.register(
                _service("r"), scope_kind=ScopeKind.PROCESS, thread_safety="maybe-fine"
            )

        assert "无法识别" in str(exc.value)

    @pytest.mark.parametrize(
        "declaration",
        [
            ThreadSafety.CONTAINER_SERIALIZED,
            ThreadSafety.INSTANCE_GUARANTEED,
            ThreadSafety.SINGLE_THREAD,
        ],
    )
    def test_each_legal_declaration_is_accepted(self, container, declaration):
        _register(container, _service(f"s-{declaration}"), thread_safety=declaration)


# =============================================================================
# 5 · 注册参数校验
# =============================================================================


class TestRegistrationValidation:
    def test_unknown_scope_kind_is_rejected(self, container):
        with pytest.raises(ValueError):
            container.register(
                _service("t"),
                scope_kind="global",
                thread_safety=ThreadSafety.INSTANCE_GUARANTEED,
            )

    def test_factory_and_instance_are_mutually_exclusive(self, container):
        with pytest.raises(ValueError):
            container.register(
                _service("u"),
                scope_kind=ScopeKind.PROCESS,
                thread_safety=ThreadSafety.INSTANCE_GUARANTEED,
                factory=dict,
                instance={},
            )

    def test_preexisting_instance_is_rejected_outside_process_scope(self, container):
        """单实例与"每会话一个"相悖，静默共享会串会话."""
        with pytest.raises(ValueError):
            container.register(
                _service("v"),
                scope_kind=ScopeKind.SESSION,
                thread_safety=ThreadSafety.INSTANCE_GUARANTEED,
                instance=_service("v")(),
            )

    def test_preexisting_instance_is_used_as_is(self, container):
        target = _service("w")
        fixed = target()
        _register(container, target, instance=fixed)

        assert container.resolve(target, Scope.process()) is fixed

    def test_factory_is_used_when_given(self, container):
        target = _service("x")
        _register(container, target, factory=lambda: {"built": "by-factory"})

        assert container.resolve(target, Scope.process()) == {"built": "by-factory"}

    def test_string_target_requires_an_explicit_name(self, container):
        with pytest.raises(TypeError):
            container.register(
                "by-name",
                scope_kind=ScopeKind.PROCESS,
                thread_safety=ThreadSafety.INSTANCE_GUARANTEED,
            )

    def test_string_target_with_a_name_resolves(self, container):
        container.register(
            "by-name",
            scope_kind=ScopeKind.PROCESS,
            thread_safety=ThreadSafety.INSTANCE_GUARANTEED,
            name="by-name",
            factory=lambda: "built-by-name",
        )

        assert container.resolve("by-name", Scope.process()) == "built-by-name"


# =============================================================================
# 6 · 并发解析只构造一次
# =============================================================================


class TestConcurrentResolutionConstructsOnce:
    """同一注册项并发解析 MUST 只构造一个实例.

    这是 check-then-act 的经典失守点（`EventChannelRegister.get_channel` 正是如此）：
    map 线程安全不代表"查不到就建"这一步是原子的，两个线程会各建一个再丢掉一个。
    """

    def test_concurrent_resolve_yields_one_instance(self, container):
        import threading
        import time

        constructed = []
        # 栅栏放在**解析之前**，让 8 个线程尽可能同时进入"未缓存"阶段；
        # 不能放在工厂里——工厂按设计只会被调用一次，等 8 个的栅栏必然破裂
        start = threading.Barrier(8)

        def build():
            constructed.append(1)
            time.sleep(0.05)  # 拉长构造窗口，否则先到的线程可能在其余线程启动前就完成
            return object()

        target = _service("concurrent")
        _register(container, target, factory=build)
        scope = Scope.process()

        results = [None] * 8

        def worker(index):
            start.wait(timeout=5)
            results[index] = container.resolve(target, scope)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert len(constructed) == 1, f"构造了 {len(constructed)} 次"
        assert all(result is results[0] for result in results), "并发解析返回了不同实例"
