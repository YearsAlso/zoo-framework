"""add-adaptive-scheduling：bandit 决策与 DualArmWorker 的回归测试.

覆盖 spec delta 的各 Scenario（注入固定随机源与 fake 适配器/决策器，不需要
真实 Rust 扩展）：

- EpsilonGreedy：均值更新数学正确（增量式 = 全量均值）、ε=0 稳定选优臂、
  无样本/均值相等的固定保守侧、ε 探索分布（固定种子统计断言）
- BanditPolicy：同名类共享统计（key=类名）、reset 清零、类目惰性建档、
  逐类探索率覆盖、并发 record 无交错损坏
- DualArmWorker：双臂决策闭环、奖励来自实测时长且按实际臂记录、
  关闭零影响（不进 bandit 分支）、native 未启用显式拒绝、fail-open、hooks 契约
- 接线：决策在 worker 内完成，调度内核（WorkerDispatchCore）零感知

断言纪律（assertion-integrity）：统计的可变断言一律经调用时快照或
snapshot() 新 dict；fake 侧记录调用当时实参，验证期只读快照。
"""

import importlib
import random
import threading
import time

import pytest

from zoo_framework.core.adaptive import (
    ARM_NATIVE,
    ARM_PYTHON,
    EpsilonGreedy,
    get_bandit_policy,
    reset_bandit_policy,
)
from zoo_framework.core.adaptive.bandit import _DEFAULT_ARM

# =============================================================================
# 参数键族
# =============================================================================


class TestAdaptiveParams:
    params_module = importlib.import_module("zoo_framework.core.aop.params")

    def test_adaptive_keys_resolve(self, monkeypatch):
        """嵌套 config 解析（复用 native 键族测试形态）."""
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.core.params_path import param

        monkeypatch.setattr(
            ParamsFactory,
            "config_params",
            {"adaptive": {"enabled": True, "exploration": 0.2}},
            raising=False,
        )
        monkeypatch.setattr(self.params_module, "config_params", {}, raising=False)

        cls = type(
            "AdaptiveParamsFresh",
            (),
            {
                "ADAPTIVE_ENABLED": param(value="adaptive:enabled", default=False),
                "EXPLORATION": param(value="adaptive:exploration", default=0.05),
            },
        )
        resolved = self.params_module.params(cls)
        assert resolved.ADAPTIVE_ENABLED is True
        assert pytest.approx(0.2) == resolved.EXPLORATION

    def test_defaults_conservative(self, monkeypatch):
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.core.params_path import param

        monkeypatch.setattr(ParamsFactory, "config_params", {}, raising=False)
        monkeypatch.setattr(self.params_module, "config_params", {}, raising=False)
        cls = type(
            "AdaptiveParamsOff",
            (),
            {"ADAPTIVE_ENABLED": param(value="adaptive:enabled", default=False)},
        )
        resolved = self.params_module.params(cls)
        assert resolved.ADAPTIVE_ENABLED is False


# =============================================================================
# EpsilonGreedy
# =============================================================================


class TestEpsilonGreedy:
    def test_incremental_mean_equals_batch_mean(self):
        """增量均值与全量均值数学等价（喂同一序列后比对）."""
        rng = random.Random(42)
        samples_native = [0.1 + rng.random() for _ in range(50)]
        samples_python = [0.3 + rng.random() for _ in range(50)]

        online = EpsilonGreedy(epsilon=0)
        for n_dur, p_dur in zip(samples_native, samples_python, strict=False):
            online.record(ARM_NATIVE, n_dur)
            online.record(ARM_PYTHON, p_dur)

        snap = online.snapshot()
        assert snap[ARM_NATIVE]["mean"] == pytest.approx(sum(samples_native) / 50)
        assert snap[ARM_PYTHON]["mean"] == pytest.approx(sum(samples_python) / 50)
        assert snap[ARM_NATIVE]["n"] == 50 and snap[ARM_PYTHON]["n"] == 50

    def test_zero_epsilon_stably_picks_better_arm(self):
        """ε=0：native 均值更低（更快）→ 稳定选 native."""
        greedy = EpsilonGreedy(epsilon=0)
        for i in range(10):
            greedy.record(ARM_NATIVE, 0.1 + i * 0.001)
            greedy.record(ARM_PYTHON, 0.5)
        decisions = {greedy.decide(random.Random(1)) for _ in range(50)}
        assert decisions == {ARM_NATIVE}

    def test_no_samples_defaults_to_python(self):
        """两臂皆无样本 → 固定保守侧（python），可复现."""
        greedy = EpsilonGreedy(epsilon=0)
        assert greedy.decide(random.Random(0)) == _DEFAULT_ARM == ARM_PYTHON

    def test_equal_means_defaults_to_python(self):
        """均值相等 → 固定保守侧，不抖动."""
        greedy = EpsilonGreedy(epsilon=0)
        for _ in range(5):
            greedy.record(ARM_NATIVE, 0.2)
            greedy.record(ARM_PYTHON, 0.2)
        decisions = {greedy.decide(random.Random(7)) for _ in range(20)}
        assert decisions == {ARM_PYTHON}

    def test_unsampled_arm_loses_to_measured(self):
        """只有单臂有样本 → 决策该臂（两个方向各自成立）."""
        only_python = EpsilonGreedy(epsilon=0)
        only_python.record(ARM_PYTHON, 1.0)
        assert only_python.decide(random.Random(0)) == ARM_PYTHON

        only_native = EpsilonGreedy(epsilon=0)
        only_native.record(ARM_NATIVE, 1.0)
        assert only_native.decide(random.Random(0)) == ARM_NATIVE

    def test_exploration_rate_statistics(self):
        """ε=0.3 且 native 显著更优 → 随机探索约 15% 落在 python 臂（固定种子）."""
        greedy = EpsilonGreedy(epsilon=0.3)
        for _ in range(10):
            greedy.record(ARM_NATIVE, 0.01)
            greedy.record(ARM_PYTHON, 1.0)
        rng = random.Random(2026)
        total, python_picks = 2000, 0
        for _ in range(total):
            if greedy.decide(rng) == ARM_PYTHON:
                python_picks += 1
        # 期望 ≈ (0.3/2) × 2000 = 300；宽区间容忍统计涨落
        assert 180 <= python_picks <= 450, f"探索分布异常: {python_picks}/{total}"

    def test_epsilon_clamped(self):
        assert EpsilonGreedy(epsilon=1.5).epsilon < 1.0
        assert EpsilonGreedy(epsilon=-1).epsilon == 0.0

    def test_unknown_arm_loudly_rejected(self):
        greedy = EpsilonGreedy(epsilon=0)
        with pytest.raises(KeyError):
            greedy.record("third_arm", 0.1)

    def test_snapshot_is_isolated_copy(self):
        """snapshot 返回新 dict：改动快照不影响内部统计."""
        greedy = EpsilonGreedy(epsilon=0)
        greedy.record(ARM_NATIVE, 0.5)
        snap = greedy.snapshot()
        snap[ARM_NATIVE]["mean"] = 999.0
        assert greedy.snapshot()[ARM_NATIVE]["mean"] == pytest.approx(0.5)


# =============================================================================
# BanditPolicy
# =============================================================================


class TestBanditPolicy:
    def setup_method(self):
        reset_bandit_policy()

    def test_same_class_name_shares_stats(self):
        """同名类的多实例共享统计（key=类名，实例后缀不进 key）."""
        policy = get_bandit_policy()
        policy.record("ModbusWorker", ARM_NATIVE, 0.05)
        policy.record("ModbusWorker", ARM_NATIVE, 0.07)
        snap = policy.snapshot()
        assert len(snap) == 1
        assert snap["ModbusWorker"][ARM_NATIVE]["n"] == 2
        assert snap["ModbusWorker"][ARM_NATIVE]["mean"] == pytest.approx(0.06)

    def test_different_classes_isolated(self):
        policy = get_bandit_policy()
        policy.record("WorkerA", ARM_NATIVE, 0.1)
        policy.record("WorkerB", ARM_PYTHON, 0.2)
        snap = policy.snapshot()
        assert set(snap) == {"WorkerA", "WorkerB"}

    def test_decision_after_updates_prefers_faster_arm(self):
        policy = get_bandit_policy()
        for _ in range(20):
            policy.record("Fast", ARM_NATIVE, 0.01)
            policy.record("Fast", ARM_PYTHON, 0.5)
        assert policy.decide("Fast") == ARM_NATIVE

    def test_per_class_epsilon_override(self, monkeypatch):
        """``adaptive:explorationOverride`` 键族覆盖类目探索率."""
        from zoo_framework.core.params_factory import ParamsFactory

        monkeypatch.setattr(
            ParamsFactory,
            "config_params",
            {"adaptive": {"explorationOverride": {"PingWorker": 0.9}}},
            raising=False,
        )
        policy = get_bandit_policy()
        assert policy._greedy_for("PingWorker").epsilon == pytest.approx(0.9)
        assert policy._greedy_for("OtherWorker").epsilon == pytest.approx(0.05)

    def test_reset_clears_singleton(self):
        first = get_bandit_policy()
        first.record("X", ARM_NATIVE, 0.1)
        reset_bandit_policy()
        second = get_bandit_policy()
        assert first is not second
        assert second.snapshot() == {}

    def test_concurrent_record_no_corruption(self):
        """并发 record 无交错损坏：10 线程 × 各 40 次，n 与均值精确可复核."""
        policy = get_bandit_policy()
        barrier = threading.Barrier(10)

        def run():
            barrier.wait()
            for _ in range(40):
                policy.record("Conc", ARM_NATIVE, 0.1)

        threads = [threading.Thread(target=run) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        snap = policy.snapshot()
        assert snap["Conc"][ARM_NATIVE]["n"] == 400
        assert snap["Conc"][ARM_NATIVE]["mean"] == pytest.approx(0.1)


# =============================================================================
# DualArmWorker
# =============================================================================


class FakePolicy:
    """fake 决策器：调用时快照记录（assertion-integrity），预置决策臂."""

    def __init__(self, arm):
        self.arm = arm
        self.records: list[tuple[str, str]] = []
        self.durations: list[float] = []

    def decide(self, class_name):
        return self.arm

    def record(self, class_name, arm, duration):
        self.records.append((class_name, arm))  # 调用时快照
        self.durations.append(duration)


class FakeNativeAdapter:
    """fake 原生适配器：记录调用并返回固定产物（对象构造后不改写，按值断言）."""

    def __init__(self):
        self.executed: list[tuple[str, bytes]] = []

    def ensure_ready(self) -> None:
        pass

    def contract(self, task_name):
        from zoo_framework.native import NativeTaskContract

        return NativeTaskContract(
            name=task_name,
            contract_version=1,
            input_format="bytes",
            max_input_bytes=None,
            output_format="bytes",
        )

    def execute(self, task_name, payload):
        self.executed.append((task_name, payload))
        return b"native-output"

    def convert_output(self, raw, contract):
        return {"from": "native", "raw": raw.decode("utf-8")}


def _use_fake_adapter(monkeypatch, adapter):
    """把进程级 adapter 单例与握手入口在测试内指向 fake."""
    from zoo_framework.native import adapter as adapter_mod

    monkeypatch.setattr(adapter_mod, "_adapter_singleton", adapter)


def _set_adaptive_enabled(monkeypatch, enabled: bool) -> None:
    """直接改写 AdaptiveParams.ADAPTIVE_ENABLED 类属性.

    @params 在导入期把类属性改写成了**字面值**（上 точно global 注释），重复应用
    @params 是空操作——运行期 ``_execute`` 读的是类属性，monkeypatch 类属性即生效。
    """
    from zoo_framework.params import AdaptiveParams

    monkeypatch.setattr(AdaptiveParams, "ADAPTIVE_ENABLED", enabled)


def _set_native_enabled(monkeypatch, enabled: bool) -> None:
    """打桩 ParamsFactory.config_params 的 native 键族.

    实现在构造期现查 ``ParamsFactory().get_params("native:enabled", ...)``，
    打桩 config 即生效；AdaptiveParams 形态的类属性补丁在这里用不上（经 factory 读）。
    """
    from zoo_framework.core.params_factory import ParamsFactory

    monkeypatch.setattr(
        ParamsFactory, "config_params", {"native": {"enabled": enabled}}, raising=False
    )


def _dual_worker(monkeypatch, policy, **props):
    """构造受测子类；声明原生臂时同步把 adapter 换成 fake 并按需启用开关.

    _flags: {"native": True} → 启用 native:enabled + adaptive（决策闭环用例的前提：
    默认两开关都关着，而类属性/开关已冻结、必须显式打开）。
    """
    from zoo_framework.workers import DualArmWorker

    flags = props.pop("_flags", {})
    adapter = None
    if "native_task_name" in props:
        adapter = FakeNativeAdapter()
        _use_fake_adapter(monkeypatch, adapter)
        if flags.get("native", False):
            _set_adaptive_enabled(monkeypatch, True)
            _set_native_enabled(monkeypatch, True)

    class DemoDual(DualArmWorker):
        def _execute_python(self):
            return {"from": "python"}

    worker = DemoDual({"name": "Demo", "is_loop": False, **props}, policy=policy)
    return worker, adapter


def _build_declared_class(monkeypatch, *, native_enabled: bool):
    """构造「声明原生臂且静态路由」的受测类与 fake 适配器（不经决策器）.

    native_enabled 决定开关层的配置桩：显式拒绝用例传 False，扩展拒绝用例传 True。
    """
    from zoo_framework.workers import DualArmWorker

    adapter = FakeNativeAdapter()
    _use_fake_adapter(monkeypatch, adapter)
    _set_native_enabled(monkeypatch, native_enabled)

    class StaticNative(DualArmWorker):
        def _execute_python(self):
            return {"from": "python"}

    return StaticNative, adapter


class TestDualArmWorker:
    def test_missing_python_arm_rejected(self):
        """未实现 _execute_python 的子类 → 构造期大声报错."""
        from zoo_framework.workers import DualArmWorker

        class Broken(DualArmWorker):
            pass  # 未实现 python 臂

        with pytest.raises(NotImplementedError, match="_execute_python"):
            Broken({"name": "B"})

    def test_native_disabled_explicitly_rejected(self, monkeypatch):
        """Scenario: native:enabled=false → 构造期 RuntimeError，无一次静默执行."""

        _set_native_enabled(monkeypatch, False)
        worker_cls, adapter = _build_declared_class(monkeypatch, native_enabled=False)
        with pytest.raises(RuntimeError, match="native:enabled"):
            worker_cls({"name": "D", "native_task_name": "t"})
        assert adapter.executed == [], "拒绝发生在构造期，扩展 MUST NOT 被执行"

    def test_native_extension_missing_explicitly_rejected(self, monkeypatch):
        """Scenario: 开关开着但扩展不可用 → ensure_ready 的 NativeInvalidInput 上抛.

        不能经 _build_declared_class 构造：它会把进程级 adapter 桩换成
        FakeNativeAdapter，覆盖掉本用例特意注入的 NeverReady。
        """
        from zoo_framework.native import adapter as adapter_mod
        from zoo_framework.workers import DualArmWorker

        class NeverReady:
            def ensure_ready(self):
                raise adapter_mod.NativeInvalidInput("原生扩展模块 'zoo_framework_native' 未安装")

        monkeypatch.setattr(adapter_mod, "_adapter_singleton", NeverReady())
        _set_native_enabled(monkeypatch, True)

        class StaticNative(DualArmWorker):
            def _execute_python(self):
                return {"from": "python"}

        with pytest.raises(adapter_mod.NativeInvalidInput, match="未安装"):
            StaticNative({"name": "D", "native_task_name": "t"})

    def test_python_arm_decision_when_policy_says_python(self, monkeypatch):
        """决策臂 python → python 执行体被调用、native 从未被触碰."""
        policy = FakePolicy(ARM_PYTHON)
        worker, adapter = _dual_worker(
            monkeypatch,
            policy,
            native_task_name="modbus_rtu.parse_response",
            input=b"\x01",
            _flags={"native": True},
        )
        result = worker._execute()
        assert result == {"from": "python"}
        assert adapter.executed == [], "决策 python 时原生执行体 MUST NOT 被调用"
        assert policy.records == [("DemoDual", ARM_PYTHON)] * 1

    def test_native_arm_decision_routes_to_adapter(self, monkeypatch):
        """决策臂 native → adapter 按契约执行，输出经 convert_output."""
        policy = FakePolicy(ARM_NATIVE)
        worker, adapter = _dual_worker(
            monkeypatch,
            policy,
            native_task_name="modbus_rtu.parse_response",
            input=b"\x01\x03\x02",
            _flags={"native": True},
        )
        result = worker._execute()
        assert result == {"from": "native", "raw": "native-output"}
        assert adapter.executed == [("modbus_rtu.parse_response", b"\x01\x03\x02")]
        assert policy.records == [("DemoDual", ARM_NATIVE)]

    def test_reward_is_measured_duration_not_constant(self, monkeypatch):
        """奖励 = 实测时长（>0，且两次执行必然可复现地非定值——非写常量）."""
        policy = FakePolicy(ARM_PYTHON)
        from zoo_framework.workers import DualArmWorker

        _set_adaptive_enabled(monkeypatch, True)

        class SlowDemo(DualArmWorker):
            def _execute_python(self):
                time.sleep(0.005)
                return {"slept": True}

        # 有决策记录的前提是声明了双臂（无声明 → 纯 python，不进闭环——上一用例的语义）
        adapter = FakeNativeAdapter()
        _use_fake_adapter(monkeypatch, adapter)
        _set_native_enabled(monkeypatch, True)
        worker = SlowDemo({"name": "S", "is_loop": False, "native_task_name": "t"}, policy=policy)
        worker._execute()
        worker._execute()
        assert policy.records == [("SlowDemo", ARM_PYTHON), ("SlowDemo", ARM_PYTHON)]
        assert all(d > 0.004 for d in policy.durations), (
            f"记录的时长不是实测值（应 > 5ms 计入）: {policy.durations}"
        )

    def test_disabled_zero_bandit_branch(self, monkeypatch):
        """Scenario: adaptive 关闭 → 纯 python 臂，零 bandit 分支（policy 不被触达）."""

        class ExplodingPolicy:
            def decide(self, *_):
                raise AssertionError("adaptive 关闭时 MUST NOT 触达决策器")

            def record(self, *_):
                raise AssertionError("adaptive 关闭时 MUST NOT 更新统计")

        from zoo_framework.workers import DualArmWorker

        class Demo(DualArmWorker):
            def _execute_python(self):
                return {"plain": True}

        _set_adaptive_enabled(monkeypatch, False)
        worker = Demo({"name": "D", "is_loop": False}, policy=ExplodingPolicy())
        assert worker._execute() == {"plain": True}

    def test_no_dual_arm_declaration_executes_python_only(self, monkeypatch):
        """未声明 native_task_name → 纯 python 臂（零决策零记录）."""
        policy = FakePolicy(ARM_NATIVE)  # 决策器拒绝被触达（见上用例的对称形态）
        worker, adapter = _dual_worker(monkeypatch, policy)
        result = worker._execute()
        assert result == {"from": "python"}
        assert policy.records == []
        assert adapter is None

    def test_policy_crash_fails_open_to_python(self, monkeypatch):
        """Scenario: 决策器异常 → fail-open 按 python 臂执行，任务正常完成."""

        class CrashingPolicy:
            def decide(self, *_):
                raise RuntimeError("决策器爆炸")

            def record(self, *_):
                pass

        worker, _adapter = _dual_worker(
            monkeypatch,
            CrashingPolicy(),
            native_task_name="t",
            input=b"\x01",
            _flags={"native": True},
        )
        result = worker._execute()
        assert result == {"from": "python"}  # 任务未被决策层异常伤害

    def test_arm_body_exception_propagates(self, monkeypatch):
        """Scenario: 双臂执行体异常照 BaseWorker 契约传播（决策层不吞）."""
        from zoo_framework.workers import DualArmWorker

        class BoomPython(DualArmWorker):
            def _execute_python(self):
                raise ValueError("python 臂故障")

        worker = BoomPython({"name": "BP", "is_loop": False}, policy=FakePolicy(ARM_PYTHON))
        with pytest.raises(ValueError, match="python 臂故障"):
            worker._execute()

    def test_hooks_follow_base_contract(self, monkeypatch):
        """生命周期 hooks：_on_create 构造期触发、_on_done 每次执行触发."""
        from zoo_framework.workers import DualArmWorker

        seen: dict[str, int] = {}

        class Hooked(DualArmWorker):
            def _execute_python(self):
                return {}

            def _on_create(self):
                seen["create"] = seen.get("create", 0) + 1

            def _on_done(self):
                seen["done"] = seen.get("done", 0) + 1

        worker = Hooked({"name": "H", "is_loop": False}, policy=FakePolicy(ARM_PYTHON))
        assert seen["create"] == 1
        worker.run()
        worker.run()
        assert seen["done"] == 2

    def test_dispatch_core_untouched(self, monkeypatch):
        """接线验收：worker 经 WorkerDispatchCore 正常派发结算，内核行为无感知."""
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore

        policy = FakePolicy(ARM_PYTHON)
        monkeypatch.setattr(
            ParamsFactory, "config_params", {"adaptive": {"enabled": True}}, raising=False
        )
        worker, _ = _dual_worker(monkeypatch, policy)
        worker.native_task_name = None  # 关闭态走纯 python 臂（本用例验证内核接线）
        core = WorkerDispatchCore()
        core.begin(worker, timeout=None)
        core.run_and_settle(worker)
        assert len(policy.records) == 0, "关闭态不触决策器"
        assert core.is_inflight(worker) is False, "结算后不再在飞（恰好一次结算语义未被破坏）"
