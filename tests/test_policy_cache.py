"""策略解析缓存（变更 cache-policy-lookup / issue #47 P1）.

三段解析语义 MUST 不因缓存而变：自报 → 按 Worker 名覆盖 → 全局默认；
falsy 值（0 / False / ""）是**有效配置值**，缓存判据是哨兵身份比较，
MUST NOT 把缓存到的 0 当未命中重新解析或穿透到默认值。
"""

import pytest

from zoo_framework.core.params_factory import ParamsFactory
from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.params import WorkerParams
from zoo_framework.workers import BaseWorker


def _worker(name: str, **props) -> BaseWorker:
    props.setdefault("name", name)
    return BaseWorker(props)


def _override_key(worker, attr: str) -> str:
    return f"{WorkerParams.WORKER_OVERRIDE_PREFIX}:{worker.name}:{attr}"


@pytest.fixture
def lookup(monkeypatch):
    """拦截 ParamsFactory.get_params：可编程返回值 + 调用计数."""
    state = {"values": {}, "calls": []}

    def fake_get_params(self, key, default_value=None):
        state["calls"].append(key)
        return state["values"].get(key, default_value)

    monkeypatch.setattr(ParamsFactory, "get_params", fake_get_params)
    return state


class TestPolicyResolutionCached:
    def test_repeated_resolution_hits_cache_once(self, lookup):
        core = WorkerDispatchCore()
        w = _worker("CacheProbe")
        lookup["values"][_override_key(w, "period")] = 2.5

        assert core.resolve_period(w) == 2.5
        period_calls_before = lookup["calls"].count(_override_key(w, "period"))
        for _ in range(10):
            assert core.resolve_period(w) == 2.5

        # 参数查询只发生首次那一次
        assert lookup["calls"].count(_override_key(w, "period")) == period_calls_before == 1

    def test_falsy_override_value_is_cached_as_valid(self, lookup):
        """显式 phase:0 是有效值：不得被当成未命中、也不得穿透到默认."""
        core = WorkerDispatchCore()
        w = _worker("ZeroPhase")
        lookup["values"][_override_key(w, "phase")] = 0

        assert core.resolve_phase(w) == 0
        calls_after_first = len(lookup["calls"])
        assert core.resolve_phase(w) == 0
        assert len(lookup["calls"]) == calls_after_first, "缓存里的 0 被判成未命中重查了"

    def test_self_reported_value_short_circuits_lookup(self, lookup):
        core = WorkerDispatchCore()
        w = _worker("SelfPeriod", period=1.0)

        assert core.resolve_period(w) == 1.0
        assert _override_key(w, "period") not in lookup["calls"]
        # 自报值同样进缓存，第二段查询从不发生
        assert core.resolve_period(w) == 1.0
        assert _override_key(w, "period") not in lookup["calls"]


class TestPolicyCacheInvalidation:
    def test_set_workers_resets_cache(self, lookup):
        core = WorkerDispatchCore()
        w = _worker("Reround")
        lookup["values"][_override_key(w, "period")] = 1.0
        assert core.resolve_period(w) == 1.0

        core.set_workers([w])
        lookup["values"][_override_key(w, "period")] = 9.0

        assert core.resolve_period(w) == 9.0, "set_workers 后仍读到旧缓存"

    def test_add_worker_same_name_resets_that_worker(self, lookup):
        core = WorkerDispatchCore()
        first = _worker("Shared")
        lookup["values"][_override_key(first, "period")] = 1.0
        core.add_worker(first)
        assert core.resolve_period(first) == 1.0

        # 同名重注册（Master.register_worker 覆盖实例）：旧解析必须作废
        replacement = _worker("Shared")
        lookup["values"][_override_key(replacement, "period")] = 7.0
        core.add_worker(replacement)
        assert core.resolve_period(replacement) == 7.0

    def test_clear_resets_cache(self, lookup):
        core = WorkerDispatchCore()
        w = _worker("Cleared")
        lookup["values"][_override_key(w, "period")] = 1.0
        assert core.resolve_period(w) == 1.0

        core.clear()
        lookup["values"][_override_key(w, "period")] = 4.0
        assert core.resolve_period(w) == 4.0
