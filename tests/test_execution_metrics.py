"""执行事实接缝与健康监控接通（变更 wire-svm-metrics / issue #246）.

对应 ``openspec/changes/wire-svm-metrics/specs/`` 下的三条能力：

- ``worker-lifecycle``：执行事实经可注册的观察接缝生产；未注册观察者时行为不变；
  健康报告反映真实执行事实
- ``ci-and-packaging``：观测导出面为可选附加，默认依赖不加重
- ``docs-consistency`` / ``ai-discoverability`` 的措辞口径由既有的措辞契约测试覆盖

用例按"接缝本体 → 内核发射 → SVM 接通 → 导出面"分组。断言口径遵循
``.claude/rules/assertion-integrity.md``：``ExecutionFact`` 是不可变 dataclass，故按
引用记录即调用时的取值；所有否定式断言前先断言正向事实成立（非空前置）。
"""

import dataclasses
import importlib.util
import threading
import time
import tomllib
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from zoo_framework.core.container import framework_container
from zoo_framework.core.execution_metrics import (
    ExecutionFact,
    ExecutionObserverRegistry,
    emit_execution_fact,
)
from zoo_framework.core.master import Master, MasterConfig, SVMWorker
from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.observability import OtlpMetricExporter, PrometheusTextExporter
from zoo_framework.workers import BaseWorker

REPO_ROOT = Path(__file__).resolve().parents[1]


def _wait_until(predicate, timeout: float = 10.0, interval: float = 0.01) -> bool:
    """等待条件成立；超时返回最后一次判定结果."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class _Recorder:
    """观察回调记录器：按调用先后顺序保存收到的事实.

    ``ExecutionFact`` 是 frozen dataclass（不可变），因此列表里的引用即调用当时的取值，
    不存在"验证期读到最终内存态"的陷阱。
    """

    def __init__(self):
        self.facts: list[ExecutionFact] = []

    def __call__(self, fact: ExecutionFact) -> None:
        self.facts.append(fact)


# =============================================================================
# 1 · 接缝本体（ExecutionObserverRegistry）
# =============================================================================


class TestExecutionObserverSeam:
    """Scenario: 注册后收到每次执行的事实 / 未注册观察者时行为不变 / 注销后不再收到事实."""

    def test_registered_observer_receives_every_fact(self):
        """注册后的回调收到每次发射的事实，且内容与顺序一致."""
        registry = ExecutionObserverRegistry()
        recorder = _Recorder()
        registry.observe(recorder)

        emit_execution_fact("alpha", 0.5, True)
        emit_execution_fact("beta", 0.25, False)

        assert len(recorder.facts) == 2, "注册后的回调未收到全部执行事实"
        assert recorder.facts[0] == ExecutionFact("alpha", 0.5, True)
        assert recorder.facts[1] == ExecutionFact("beta", 0.25, False)

    def test_no_observer_means_emit_is_a_noop(self):
        """未注册任何回调时发射为空操作：不抛错、不残留状态（行为不变的前提）."""
        registry = ExecutionObserverRegistry()
        # 非空前置：本用例的前提是"此刻没有任何观察者"
        assert registry.observers() == (), "接缝在新实例上应无观察者"

        emit_execution_fact("alpha", 1.0, True)  # 不应抛任何异常

        assert registry.observers() == ()

    def test_unobserve_stops_delivery(self):
        """注销后不再收到事实——先证明注销前确实收到过（非空前置）."""
        registry = ExecutionObserverRegistry()
        recorder = _Recorder()
        registry.observe(recorder)

        emit_execution_fact("alpha", 0.1, True)
        assert len(recorder.facts) == 1, "注销前的正向事实未成立，本用例失去意义"

        registry.unobserve(recorder)
        emit_execution_fact("alpha", 0.2, True)

        assert len(recorder.facts) == 1, "注销后回调仍被调用"
        assert registry.observers() == (), "注销后观察者仍在册"

    def test_duplicate_registration_keeps_one_entry(self):
        """同一回调重复注册只保留一份，不会重复投递."""
        registry = ExecutionObserverRegistry()
        recorder = _Recorder()
        registry.observe(recorder)
        registry.observe(recorder)

        assert len(registry.observers()) == 1

        emit_execution_fact("alpha", 0.1, True)
        assert len(recorder.facts) == 1, "重复注册导致了重复投递"

    def test_one_observer_raising_does_not_starve_the_others(self):
        """单个回调抛错不吞掉其余回调的事实（大声失败、不静默降级）."""
        registry = ExecutionObserverRegistry()
        good = _Recorder()
        boom = _Recorder()

        def explode(fact: ExecutionFact) -> None:
            boom.facts.append(fact)
            raise RuntimeError("测试用：故意抛出的回调")

        registry.observe(explode)
        registry.observe(good)

        emit_execution_fact("alpha", 0.3, True)

        assert len(boom.facts) == 1, "抛错回调自身应已收到事实（证明它被调用了）"
        assert len(good.facts) == 1, "抛错回调拖垮了其余回调"

    def test_fact_is_immutable(self):
        """事实不可变：就地改写直接报错，消费侧无法改坏该次执行的取值."""
        fact = ExecutionFact("alpha", 0.5, True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            fact.worker_name = "beta"  # type: ignore[misc]

    def test_registry_resets_with_the_container(self):
        """注册表是进程级共享实例：容器复位后回到空表（测试隔离的机理）."""
        registry = ExecutionObserverRegistry()
        registry.observe(_Recorder())
        assert len(registry.observers()) == 1, "复位前的正向事实未成立"

        framework_container().reset()

        assert ExecutionObserverRegistry().observers() == (), "容器复位后观察者仍在册"


# =============================================================================
# 2 · 内核在唯一结算收口发射事实
# =============================================================================


class _OkWorker(BaseWorker):
    """每次执行成功的 Worker."""

    def __init__(self, name: str = "ok_worker"):
        super().__init__({"name": name, "delay_time": 0})
        self.runs = 0

    def _execute(self):
        self.runs += 1
        return "ok"


class _RaisingWorker(BaseWorker):
    """执行体抛错的 Worker——``BaseWorker.run`` 不向外抛，而是把失败封进结果（#228）."""

    def __init__(self, name: str = "bad_worker"):
        super().__init__({"name": name, "delay_time": 0})

    def _execute(self):
        raise ValueError("boom")


class TestSettleEmitsFacts:
    """Scenario: 注册后收到每次执行的事实（经真实结算路径）."""

    @pytest.fixture
    def recorder(self):
        registry = ExecutionObserverRegistry()
        recorder = _Recorder()
        registry.observe(recorder)
        return recorder

    def test_successful_settlement_emits_one_success_fact(self, recorder):
        """一次成功执行经 settle 产出恰好一条成功事实."""
        core = WorkerDispatchCore()
        worker = _OkWorker()
        core.begin(worker, None)
        core.run_and_settle(worker)

        assert len(recorder.facts) == 1, "结算未产出唯一一条执行事实"
        fact = recorder.facts[0]
        assert fact.worker_name == "ok_worker"
        assert fact.success is True
        assert fact.duration >= 0.0

    def test_failed_body_emits_failure_fact(self, recorder):
        """执行体抛错时事实标记为失败——只看 settle 的 ``error`` 会把失败记成成功."""
        core = WorkerDispatchCore()
        worker = _RaisingWorker()
        core.begin(worker, None)
        core.run_and_settle(worker)

        assert len(recorder.facts) == 1
        assert recorder.facts[0].success is False, "失败的执行被记成了成功"

    def test_identity_is_registry_name_not_instance_name(self, recorder):
        """事实的 Worker 身份是 ``registry_name``（无序号），不是带序号的实例名."""
        core = WorkerDispatchCore()
        worker = _OkWorker(name="alpha")
        core.begin(worker, None)
        core.run_and_settle(worker)

        assert worker.name == "alpha_1", "实例名形状变了，本用例的对照失去意义"
        assert recorder.facts[0].worker_name == "alpha"

    def test_settlement_still_delivers_result_without_observer(self):
        """未注册观察者时结算路径逐项不变：结果照常上报，未抛异常."""
        core = WorkerDispatchCore()
        worker = _OkWorker()
        core.begin(worker, None)
        core.run_and_settle(worker)

        assert worker.runs == 1, "未注册观察者时执行体没有被执行"
        assert core.metrics()["completed"] == 1
        assert core.metrics()["inflight"] == 0


# =============================================================================
# 3 · SVM 健康报告接通
# =============================================================================


class TestSvmHealthReport:
    """Scenario: 真实调度下执行计数非零 / 失败执行计入错误计数 / 未执行时如实为零."""

    def test_zero_before_any_execution(self):
        """未发生任何执行时如实为零（正向前置：登记确实生效了）."""
        svm = SVMWorker()
        svm.register_worker("alpha", object())

        health = svm.get_worker_health("alpha")
        assert health["execute_count"] == 0
        assert health["error_count"] == 0

    def test_health_reflects_emitted_facts(self):
        """健康报告随接缝事实增长——成功与失败分别计入计数."""
        svm = SVMWorker()
        svm.register_worker("alpha", object())
        svm.start_monitoring()
        try:
            emit_execution_fact("alpha", 0.5, True)
            emit_execution_fact("alpha", 0.25, True)
            emit_execution_fact("alpha", 0.1, False)
            health = svm.get_worker_health("alpha")
        finally:
            svm.stop_monitoring()

        assert health["execute_count"] == 3
        assert health["error_count"] == 1
        assert health["health_score"] == 66
        assert health["avg_execute_time"] == pytest.approx(0.85 / 3)

    def test_stop_monitoring_unobserves(self):
        """停机后不再累加（注销生效）——先证明停机前确实累加过."""
        svm = SVMWorker()
        svm.register_worker("alpha", object())
        svm.start_monitoring()
        emit_execution_fact("alpha", 0.1, True)
        assert svm.get_worker_health("alpha")["execute_count"] == 1, "停机前的正向事实未成立"

        svm.stop_monitoring()
        emit_execution_fact("alpha", 0.1, True)

        assert svm.get_worker_health("alpha")["execute_count"] == 1, "停机后仍在累加指标"

    def test_svm_disabled_leaves_no_observer(self):
        """``enable_svm=False`` 时零观察者：接缝空转，健康报告如实为空（行为不变）."""
        master = Master(MasterConfig(enable_svm=False))
        try:
            assert master.svm_worker is None
            assert master.get_health_report() == {}
            assert ExecutionObserverRegistry().observers() == (), "SVM 未启用却注册了观察者"
        finally:
            master.shutdown()


class TestRealSchedulingKeepsHealthReal:
    """Scenario: 真实调度下执行计数非零（README 限制表那行 ⚠️ 的验收）."""

    class _OneShotWorker(BaseWorker):
        def __init__(self):
            super().__init__({"name": "one_shot", "is_loop": False, "delay_time": 0})

        def _execute(self):
            return "ok"

    def test_execute_count_is_nonzero_under_real_scheduling(self):
        """经真实调度轮次派发一次后，健康报告的 execute_count 为非零实数."""
        master = Master()
        try:
            master.register_worker("one_shot", self._OneShotWorker)

            def _ran() -> bool:
                master.waiter.execute_service()
                report = master.get_health_report()
                return report.get("one_shot", {}).get("execute_count", 0) > 0

            assert _wait_until(_ran), (
                f"真实调度下 execute_count 仍为零：{master.get_health_report()}"
            )
            health = master.get_health_report()["one_shot"]
            assert health["error_count"] == 0
            assert health["health_score"] == 100
        finally:
            master.shutdown()


# =============================================================================
# 4 · 导出面（可选附加 + 示例）
# =============================================================================


def _load_example(module_name: str, filename: str):
    """按文件路径加载示例模块（example/ 不是包的一部分，不能直接 import）."""
    path = REPO_ROOT / "example" / "observability" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, f"无法加载示例 {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPrometheusExporter:
    """Scenario: Prometheus 文本渲染含真实计数."""

    def test_render_contains_real_counts(self):
        """渲染出的文本行携带接缝累积的真实计数，注销后不再增长."""
        exporter = PrometheusTextExporter()
        exporter.observe()
        try:
            emit_execution_fact("alpha", 0.5, True)
            emit_execution_fact("alpha", 1.5, False)
            emit_execution_fact("beta", 0.1, True)
            snapshot = exporter.snapshot()
            exporter.close()
            emit_execution_fact("alpha", 9.9, True)
        finally:
            exporter.close()

        assert snapshot["alpha"]["execute_count"] == 2
        assert snapshot["alpha"]["error_count"] == 1
        assert snapshot["beta"]["execute_count"] == 1
        assert snapshot["beta"]["error_count"] == 0
        assert snapshot["alpha"]["total_duration"] == pytest.approx(2.0)

        text = exporter.render()
        assert 'zoo_worker_execute_count{worker="alpha"} 2' in text
        assert 'zoo_worker_error_count{worker="alpha"} 1' in text
        assert 'zoo_worker_execute_count{worker="beta"} 1' in text
        # 注销后继续发射 MUST NOT 影响已渲染的快照
        assert 'zoo_worker_execute_count{worker="alpha"} 3' not in text

    def test_example_endpoint_serves_metrics(self):
        """示例的 HTTP 端点端到端可跑通：`/metrics` 返回渲染文本，其它路径 404."""
        module = _load_example("_zoo_prometheus_example", "prometheus_endpoint.py")
        exporter = PrometheusTextExporter()
        exporter.observe()
        module.MetricsHandler.exporter = exporter

        server = ThreadingHTTPServer(("127.0.0.1", 0), module.MetricsHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            emit_execution_fact("tick_worker", 0.02, True)
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with urllib.request.urlopen(f"{base}/metrics", timeout=5) as response:
                body = response.read().decode("utf-8")
            assert 'zoo_worker_execute_count{worker="tick_worker"} 1' in body

            with pytest.raises(urllib.error.HTTPError) as excinfo:
                urllib.request.urlopen(f"{base}/nope", timeout=5)
            assert excinfo.value.code == 404
        finally:
            server.shutdown()
            server.server_close()
            exporter.close()


class TestOtlpExporter:
    """Scenario: 缺可选附加时显式报错（指名安装方式，不静默回退）."""

    def test_missing_extra_raises_actionable_error(self, monkeypatch):
        """``opentelemetry*`` 不可导入时，构造即抛出指名安装方式的显式错误.

        把导入整体阻断而不是依赖"本机恰好没装"：本机若装了附加，真实的失败分支就永远
        跑不到，这条断言会退化成摆设。
        """
        import builtins

        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError(f"No module named {name!r}", name=name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked_import)

        with pytest.raises(RuntimeError) as excinfo:
            OtlpMetricExporter()

        message = str(excinfo.value)
        assert "pip install zoo-framework[otel]" in message, "报错没有指名安装方式"
        assert "missing: opentelemetry" in message


class TestPackagingSurface:
    """Scenario: 默认依赖不含导出上游."""

    def test_otel_extra_declared_and_defaults_unchanged(self):
        """`otel` 附加声明了 OTel 上游；默认 `dependencies` 不含它."""
        data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = data["project"]

        extras = project["optional-dependencies"]
        assert "otel" in extras, "pyproject.toml 缺少 otel 可选附加"
        assert any(dep.startswith("opentelemetry") for dep in extras["otel"])

        assert not any(dep.startswith("opentelemetry") for dep in project["dependencies"]), (
            "OTel 上游被写进了默认依赖——默认「纯 Python」的负担被加重"
        )
