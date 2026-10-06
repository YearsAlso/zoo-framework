"""公共导出面一致性（变更 cleanup-aop-public-surface / issue #49）.

把"导出了但不生效"变成测试可拦截的形态：三个公共 `__all__` 的精确白名单快照 +
判废名不得回流的负断言 + 遗留 `@worker` 路径的弃用警告。"每项导出都接通真实路径"
的逐项行为证据由既有规格用例承担（config-resolution / event-dispatch /
worker-scheduling）；新增导出项必须先改动这里的白名单，评审时逼出"接通了吗"的回答。
"""

import importlib

import pytest

import zoo_framework.core as core_pkg
import zoo_framework.core.aop as aop_pkg
import zoo_framework.core.worker_registry as worker_registry_pkg

# 各包面在清理后的精确导出集合。改动任何一项都必须同步改动对应规格。
CORE_ALL = {"Master", "ParamsFactory", "ParamsPath", "event", "param"}
AOP_ALL = {"config_funcs", "configure", "event", "logger", "params", "stopwatch"}
WORKER_REGISTRY_ALL = {"WorkerRegistration", "WorkerRegistry", "get_worker_registry"}

# 判废名（issue #49）：MUST NOT 回流到任何一个公共面。
DEAD_NAMES = frozenset(
    {"worker", "worker_register", "register_worker", "validation", "validation_params"}
)


class TestPublicSurfaceWhitelists:
    """`__all__` 快照断言：导出面 == 白名单，多一项少一项都红."""

    def test_core_all_matches_whitelist(self):
        assert set(core_pkg.__all__) == CORE_ALL

    def test_aop_all_matches_whitelist(self):
        assert set(aop_pkg.__all__) == AOP_ALL

    def test_worker_registry_all_matches_whitelist(self):
        assert set(worker_registry_pkg.__all__) == WORKER_REGISTRY_ALL


class TestDeadNamesNotExported:
    """判废名不得出现在任何公共 `__all__`；被删的模块不得仍可导入."""

    @pytest.mark.parametrize(
        "module",
        [core_pkg, aop_pkg, worker_registry_pkg],
        ids=["core", "core.aop", "worker_registry"],
    )
    def test_dead_names_absent_from_all(self, module):
        leaked = DEAD_NAMES.intersection(set(module.__all__))
        assert not leaked, f"{module.__name__}.__all__ 泄漏判废项: {sorted(leaked)}"

    def test_register_worker_decorator_removed(self):
        """装饰器整删（区别于 Master.register_worker 方法——那是真实路径）。"""
        assert not hasattr(worker_registry_pkg, "register_worker")

    def test_validation_module_deleted(self):
        with pytest.raises(ImportError):
            importlib.import_module("zoo_framework.core.aop.validation")


class TestLegacyWorkerDecoratorDeprecation:
    """遗留 @worker 路径保留一个 minor 周期，但使用时必须出声."""

    def test_worker_emits_deprecation_warning(self):
        from zoo_framework.core.aop import worker as worker_module
        from zoo_framework.workers import BaseWorker

        class _Probe(BaseWorker):
            def __init__(self):
                BaseWorker.__init__(self, {"name": "DeprecationProbe"})

        with pytest.warns(DeprecationWarning, match="不接通调度"):
            decorated = worker_module.worker(count=1)(_Probe)

        # 弃用周期内行为不变：类原样返回（类型契约未破坏）
        assert decorated is _Probe

    def test_validation_module_gone_from_aop_namespace(self):
        """aop 包命名空间不再代理 validation（模块已删、导出已撤）。

        注：`worker` 不在这里断言——子模块被任何测试导入后会绑回父包命名空间
        （Python 导入机制），"不得代理"对它可测的形态只有 `__all__` 负断言（已在
        TestDeadNamesNotExported）。
        """
        assert not hasattr(aop_pkg, "validation")
