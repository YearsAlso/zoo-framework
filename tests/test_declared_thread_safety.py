"""固定框架自身那两处**如实**的线程安全归属声明（fix-container-spec-baseline 第 3.3 步）.

对应 `openspec/changes/fix-container-spec-baseline/specs/scoped-container/spec.md` 的：

- 线程安全归属声明 MUST 与实例实际行为相符
- 该判定有可核对依据

背景：清点 8 处 `@cage` 使用点时发现两处**不对**——`EventRegister` 的 `event_list` 是裸
`list`（既不加锁也不可变），`WaiterResultReactor` 继承的 `EventReactor` 有执行期读取的可变
字段（`retry_strategy` / `retry_times`），而写入发生在派发之外、两者之间没有栅栏。实现据此
把它们的归属声明为 `SINGLE_THREAD` 而**不是**想当然的 `INSTANCE_GUARANTEED`——因为**一个为假
的声明比不声明更糟**，它把未验证的安全假设写进代码。

本文件的作用是**把这两处声明钉住**：将来若有人把它们静默"升级"为 `INSTANCE_GUARANTEED`
（看起来像是"改进"），用例会转红，迫使其先说明为什么这两个实例现在能自保了。
"""

import pytest

from zoo_framework.core.container import ThreadSafety, framework_container
from zoo_framework.event.event_register import EventRegister
from zoo_framework.reactor.event_reactor_manager import EventReactorManager
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor

# 清点时判定为"无自保能力"的两处，故声明必须是 SINGLE_THREAD
ITEMS_WITHOUT_SELF_PROTECTION = (EventRegister, WaiterResultReactor)


def _declared(cls) -> str:
    return framework_container().get_registration(cls).thread_safety


class TestDeclarationsMatchActualBehaviour:
    """声明须与实际行为相符，且两处已知无自保能力的项不得声明为"实例自身保证"."""

    @pytest.mark.parametrize("cls", ITEMS_WITHOUT_SELF_PROTECTION)
    def test_declared_single_thread_not_instance_guaranteed(self, cls):
        """这两处 MUST 是 SINGLE_THREAD；改成 INSTANCE_GUARANTEED 会让本用例转红."""
        declared = _declared(cls)

        assert declared == ThreadSafety.SINGLE_THREAD, (
            f"{cls.__name__} 的归属声明是 {declared!r}。它自身不加锁且可能在执行期被"
            f"无栅栏读写，声明为 {ThreadSafety.INSTANCE_GUARANTEED!r} 会把未验证的"
            f"安全假设写进代码——若确实已能自保，请先补上锁或把字段冻结，再来改这里"
        )

    def test_event_register_basis_is_checkable(self):
        """依据可核对：`EventRegister.event_list` 确实是**裸 list**（无锁、非不可变）.

        这条不是"补充说明"，而是让上面那条断言有可追溯的依据——否则它只是一个口头结论。
        """
        instance = EventRegister()
        assert isinstance(instance.event_list, list), "依据已变，上面的声明需要重新评估"
        assert not hasattr(instance, "_lock"), "若已加锁，则应改声明并在此说明"

    def test_reactor_basis_is_checkable(self):
        """依据可核对：`EventReactor` 的可变字段确实在执行期被读取.

        `EventReactor._execute` 读 `retry_strategy` / `retry_times`，而 `worker_names` /
        `on_result` 由调用方在派发之外赋值——两者之间没有栅栏。
        """
        reactor = WaiterResultReactor()
        assert hasattr(reactor, "retry_times") and hasattr(reactor, "retry_strategy")
        assert hasattr(reactor, "worker_names"), "写入侧字段"

    def test_other_ex_caged_items_are_instance_guaranteed(self):
        """对照组：其余各处确实声明为实例自身保证——避免"一律降级"式的假修复.

        若为了消除风险把**所有**项都改成 SINGLE_THREAD，那是在放宽约束而不是如实声明，
        所以这两组要能同时成立。
        """
        for cls in (EventReactorManager,):
            assert _declared(cls) == ThreadSafety.INSTANCE_GUARANTEED, cls.__name__

    @pytest.mark.parametrize("cls", ITEMS_WITHOUT_SELF_PROTECTION)
    def test_declaration_is_one_of_the_legal_values(self, cls):
        """声明必须落在合法取值内——避免"写错了但没人发现"的静默情形."""
        assert _declared(cls) in ThreadSafety.ALL


# 注：声明 `CONTAINER_SERIALIZED` 时"绕开独占入口的直接取用 MUST 被拒绝"这一 scenario，
# 其实现级用例在 `tests/test_container_lifecycle.py`
# （`test_resolve_is_refused_and_points_at_exclusive`）。此处不重复：合成项上的覆盖比在
# 框架自身的项上再测一遍更直接，而框架自身当前没有 `CONTAINER_SERIALIZED` 项。
