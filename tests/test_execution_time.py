"""scheduler-model-seam 的 execution-time 组回归测试.

对应 openspec/changes/scheduler-model-seam/specs/execution-time/spec.md：

- 3.1 时间计算 MUST 以单调时钟为基准；墙钟 MUST NOT 参与任何区间运算
- 3.2 周期与相位 MUST 由 Worker 逐个声明，且排期 MUST 不累积漂移
- 3.3 单轮超周期时 MUST 跳过错过的轮次并计数
- 3.4 抖动 MUST 按 Worker 观测（最近 / 上界 / 样本数）
- 3.5 截止期 MUST 可分别施加于事件与派发，并在超过时熔断

用例分两类：

- **机制守护**：先证明判定机制本身有效——否则"不受墙钟影响"可能只是因为
  该判定从不生效，那样的绿是假的。
- **缺陷复现**：事件层原先用墙钟做区间运算，墙钟跳变会误判超时与等待加成。

周期排期的用例全部通过**注入 now**（单调时刻）驱动，不依赖真实等待，
因此在任意平台上都确定。
"""

import time

import pytest

from zoo_framework.core.params_factory import ParamsFactory
from zoo_framework.core.waiter.dispatch_core import JITTER_NOT_APPLICABLE, WorkerDispatchCore
from zoo_framework.fifo.node.event_fifo_node import EventNode, EventPriorityCalculator
from zoo_framework.workers import BaseWorker


def _periodic_worker(name="P", period=1.0, phase=0.0):
    """构造一个声明了周期的 Worker."""
    return BaseWorker({"name": name, "is_loop": True, "period": period, "phase": phase})


def _event_worker(name="E"):
    """构造一个未声明周期的 Worker（事件驱动语义）."""
    return BaseWorker({"name": name, "is_loop": True})


# =============================================================================
# 3.1 · 单调时间基准
# =============================================================================


class TestEventExpiryTimeBase:
    """时间计算 MUST 以单调时钟为基准（事件的超时判定）."""

    def test_expiry_mechanism_works(self):
        """机制守护：真的超时后 MUST 判定为已过期.

        没有这一条，下面的"不受墙钟影响"可能只是因为超时判定从未生效。
        """
        node = EventNode(topic="t", content="c")
        node.set_timeout(0.05)
        assert node.is_expire() is False

        time.sleep(0.06)
        assert node.is_expire() is True

    def test_wall_clock_forward_jump_does_not_expire_event(self, monkeypatch):
        """Scenario: 墙钟被调整不影响期限判定（向前跳）."""
        real_time = time.time
        node = EventNode(topic="t", content="c")
        node.set_timeout(60)

        monkeypatch.setattr(time, "time", lambda: real_time() + 31_536_000)
        assert node.is_expire() is False, "墙钟向前跳一年被误判为超时"

    def test_wall_clock_backward_jump_does_not_unexpire_event(self, monkeypatch):
        """Scenario: 墙钟被调整不影响期限判定（向后跳）."""
        real_time = time.time
        node = EventNode(topic="t", content="c")
        node.set_timeout(0.05)
        time.sleep(0.06)
        assert node.is_expire() is True

        monkeypatch.setattr(time, "time", lambda: real_time() - 31_536_000)
        assert node.is_expire() is True, "墙钟向后跳一年把已超时的节点判成未超时"


class TestWaitBonusTimeBase:
    """抖动由单调时钟测得（等待加成不受墙钟影响）."""

    def test_wait_bonus_grows_with_real_wait(self):
        """机制守护：等待真的更久时加成真的更大."""
        fresh = EventNode(topic="t", content="c", priority=100)
        older = EventNode(topic="t", content="c", priority=100)
        older.create_time -= 10.0  # 10 秒前创建

        assert older.get_effective_priority() > fresh.get_effective_priority()

    def test_wait_bonus_ignores_wall_clock(self, monkeypatch):
        """Scenario: 等待时间由单调时钟测得，不随墙钟调整而改变."""
        real_time = time.time
        node = EventNode(topic="t", content="c", priority=100)
        baseline = node.get_effective_priority()

        monkeypatch.setattr(time, "time", lambda: real_time() + 86_400)
        after = node.get_effective_priority()

        # 若墙钟参与运算，会凭空多出最多 300*(1+1)*0.3 = 180 的等待加成
        assert after - baseline < 1.0, "等待加成随墙钟跳变"

    def test_calculator_uses_monotonic_basis(self):
        """计算器以单调时钟为基准：以墙钟值传入会被钳成零等待."""
        wall_clock_past = time.time() - 10
        bonus = EventPriorityCalculator.calculate(
            priority=100, create_time=wall_clock_past, wait_time_weight=0.5
        )
        # 墙钟值远大于单调时钟，差值被 max(0, ...) 钳为 0——这正说明基准 MUST 一致
        assert bonus == pytest.approx(100.0)

        monotonic_past = time.monotonic() - 10
        assert (
            EventPriorityCalculator.calculate(
                priority=100, create_time=monotonic_past, wait_time_weight=0.5
            )
            > 100
        )


class TestDelayNodeTimeBase:
    """延迟节点的到期判定同样以单调时钟为基准."""

    def test_expiry_mechanism_works(self):
        """机制守护：到期后判定为到期."""
        from zoo_framework.fifo.node import DelayFIFONode

        node = DelayFIFONode(value="v", index=0, expired_time=time.monotonic() - 1)
        assert node.is_expire() is True

    def test_wall_clock_forward_jump_does_not_expire_node(self, monkeypatch):
        """Scenario: 墙钟被调整不影响期限判定."""
        from zoo_framework.fifo.node import DelayFIFONode

        real_time = time.time
        node = DelayFIFONode(value="v", index=0, expired_time=time.monotonic() + 60)

        monkeypatch.setattr(time, "time", lambda: real_time() + 31_536_000)
        assert node.is_expire() is not True, "墙钟向前跳被误判为到期"


# =============================================================================
# 3.2 · 周期与相位的声明入口
# =============================================================================


class TestPeriodDeclaration:
    """周期与相位 MUST 由 Worker 逐个声明，来源优先级为 props → 按名覆盖 → 全局默认."""

    def test_worker_props_declare_period_and_phase(self):
        """Scenario: Worker 通过自身属性声明周期与相位."""
        worker = _periodic_worker(period=0.5, phase=0.25)
        assert worker.period == 0.5
        assert worker.phase == 0.25

    def test_period_defaults_to_none_and_phase_to_zero(self):
        """未声明周期 → None（按事件驱动处理）；未声明相位 → 0.0."""
        worker = _event_worker()
        assert worker.period is None
        assert worker.phase == 0.0

    def test_global_default_used_when_props_silent(self, monkeypatch):
        """Scenario: 配置入口与 props 入口结果一致（props 沉默时取全局默认）."""
        from zoo_framework.params import WorkerParams

        monkeypatch.setattr(WorkerParams, "WORKER_PERIOD", 1.5, raising=False)
        monkeypatch.setattr(WorkerParams, "WORKER_PHASE", 0.5, raising=False)

        core = WorkerDispatchCore()
        worker = _event_worker("G")
        assert core.resolve_period(worker) == 1.5
        assert core.resolve_phase(worker) == 0.5

    def test_per_name_override_wins_over_global_default(self, monkeypatch):
        """按 Worker 名的配置覆盖优先于全局默认."""
        from zoo_framework.params import WorkerParams

        worker = _event_worker("N")
        monkeypatch.setattr(WorkerParams, "WORKER_PERIOD", 1.5, raising=False)
        # 覆盖键用的是 worker.name（含自动编号后缀），不是构造时给的名字
        monkeypatch.setattr(
            ParamsFactory,
            "config_params",
            {"worker": {"override": {worker.name: {"period": 0.5, "phase": 0.25}}}},
            raising=False,
        )

        core = WorkerDispatchCore()
        assert core.resolve_period(worker) == 0.5
        assert core.resolve_phase(worker) == 0.25

    def test_props_win_over_both(self, monkeypatch):
        """Worker 自身属性优先于按名覆盖与全局默认."""
        from zoo_framework.params import WorkerParams

        worker = _periodic_worker("N", period=0.25)
        monkeypatch.setattr(WorkerParams, "WORKER_PERIOD", 1.5, raising=False)
        monkeypatch.setattr(
            ParamsFactory,
            "config_params",
            {"worker": {"override": {worker.name: {"period": 0.5}}}},
            raising=False,
        )

        assert WorkerDispatchCore().resolve_period(worker) == 0.25


# =============================================================================
# 3.3 · 绝对序列排期与跳过
# =============================================================================


class TestPeriodicScheduling:
    """周期 MUST 以声明序列为基准排期、不累积漂移；超周期时跳过并计数."""

    def test_due_at_base_then_not_until_next_period(self):
        """机制守护：首次到点后，未到下一个理论时刻则不到点."""
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0)

        assert core.is_due(worker, now=100.0) is True
        assert core.is_due(worker, now=100.5) is False
        assert core.is_due(worker, now=101.0) is True

    def test_phase_offsets_first_trigger(self):
        """Scenario: 相位被遵循（首次触发相对基准存在该偏移）."""
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0, phase=0.25)

        assert core.is_due(worker, now=100.0) is False
        assert core.is_due(worker, now=100.25) is True

    def test_phase_is_not_accumulated_across_rounds(self):
        """Scenario: 多轮之间保持同一相位，不逐轮累加.

        注意：排期基准是**首次到点判定的时刻**（框架没有进程级调度纪元），
        因此先以 100.0 建立基准，首次触发才落在 100.25。
        """
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0, phase=0.25)

        assert core.is_due(worker, now=100.0) is False  # 建立基准；首次触发在 100.25
        assert core.is_due(worker, now=100.25) is True
        assert core.is_due(worker, now=101.25) is True
        assert core.is_due(worker, now=102.25) is True
        assert core.is_due(worker, now=102.5) is False

    def test_long_round_does_not_push_following_triggers(self):
        """Scenario: 执行时长不改变后续触发时刻（绝对序列，不漂移）."""
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0)

        assert core.is_due(worker, now=100.0) is True
        # 这一轮耗时 2.7 秒，跨越了 101.0 与 102.0 两个理论时刻
        assert core.is_due(worker, now=102.7) is True
        # 下一理论时刻是 103.0（基准 + 3×周期），而**不是** 102.7 + 1.0
        assert core.is_due(worker, now=102.9) is False
        assert core.is_due(worker, now=103.0) is True

    def test_missed_ticks_are_skipped_and_counted(self):
        """Scenario: 过载后不补跑；跳过次数可查询且与实际一致."""
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0)

        assert core.is_due(worker, now=100.0) is True
        assert core.skipped_count(worker) == 0

        # 到 102.7 才再次检查：理论时刻 101 由这次迟到触发覆盖，102 被跳过
        assert core.is_due(worker, now=102.7) is True
        assert core.skipped_count(worker) == 1

        # 不补跑：紧接着的检查不再触发
        assert core.is_due(worker, now=102.8) is False

    def test_no_skips_when_every_round_in_time(self):
        """Scenario: 未发生跳过时计数为零."""
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0)

        for now in (100.0, 101.0, 102.0, 103.0):
            assert core.is_due(worker, now=now) is True

        assert core.skipped_count(worker) == 0

    def test_worker_without_period_is_always_due(self):
        """Scenario: 未声明周期时按事件驱动处理（每轮都到点）."""
        core = WorkerDispatchCore()
        worker = _event_worker()

        for now in (1.0, 1.0, 1.0):
            assert core.is_due(worker, now=now) is True
        assert core.skipped_count(worker) == 0

    def test_periodic_and_event_driven_coexist(self):
        """Scenario: 周期与事件驱动可在同一进程内并存."""
        core = WorkerDispatchCore()
        periodic = _periodic_worker(period=1.0, name="P")
        event = _event_worker("E")

        assert core.is_due(event, now=100.0) is True
        assert core.is_due(periodic, now=100.0) is True
        assert core.is_due(event, now=100.1) is True, "事件驱动的 Worker 未每轮到点"
        assert core.is_due(periodic, now=100.1) is False, "周期 Worker 在周期内被提前触发"


# =============================================================================
# 3.4 · 抖动按 Worker 观测
# =============================================================================


class TestJitterObservation:
    """抖动 MUST 按 Worker 观测；未声明周期者显式标注不适用."""

    def test_worker_without_period_reports_not_applicable(self):
        """Scenario: 未声明周期的 Worker 抖动不适用."""
        core = WorkerDispatchCore()
        jitter = core.jitter(_event_worker())

        assert jitter["applicable"] is False
        assert jitter["jitter"] == JITTER_NOT_APPLICABLE
        assert jitter["jitter"] != 0, "以 0 代替'不适用'会被误读为观测到零抖动"

    def test_samples_match_trigger_count(self):
        """Scenario: 可查询最近抖动、上界与样本数，且样本数与触发次数一致."""
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0)

        for now in (100.0, 101.0, 102.0):
            core.is_due(worker, now=now)

        jitter = core.jitter(worker)
        assert jitter["applicable"] is True
        assert jitter["samples"] == 3

    def test_last_jitter_reports_latest_lateness(self):
        """最近一次抖动 = 实际触发时刻 − 理论触发时刻."""
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0)

        core.is_due(worker, now=100.0)
        core.is_due(worker, now=101.5)  # 理论 101.0，实际 101.5

        assert core.jitter(worker)["last"] == pytest.approx(0.5)

    def test_upper_bound_does_not_decrease(self):
        """Scenario: 抖动上界不因后续较小抖动而降低."""
        core = WorkerDispatchCore()
        worker = _periodic_worker(period=1.0)

        core.is_due(worker, now=100.0)  # 抖动 0
        core.is_due(worker, now=101.5)  # 理论 101.0 → 抖动 0.5
        assert core.jitter(worker)["upper_bound"] == pytest.approx(0.5)

        core.is_due(worker, now=102.0)  # 理论 102.0 → 抖动 0
        assert core.jitter(worker)["last"] == pytest.approx(0.0)
        assert core.jitter(worker)["upper_bound"] == pytest.approx(0.5), "上界被拉低"


# =============================================================================
# 3.5 · 截止期：事件侧与派发侧可独立施加
# =============================================================================


class TestEventDeadline:
    """事件侧：事件 SHALL 可承载绝对截止期并据此判定过期."""

    def test_event_with_past_deadline_is_expired(self):
        """Scenario: 事件按自身截止期判定过期."""
        node = EventNode(topic="t", content="c")
        node.set_deadline(time.monotonic() - 1)

        assert node.is_expire() is True

    def test_event_with_future_deadline_is_not_expired(self):
        node = EventNode(topic="t", content="c")
        node.set_deadline(time.monotonic() + 60)

        assert node.is_expire() is False

    def test_event_without_deadline_is_not_dropped_by_deadline(self):
        """Scenario: 未承载截止期的事件不因期限被丢弃."""
        assert EventNode(topic="t", content="c").is_expire() is False

    def test_deadline_takes_priority_over_relative_timeout(self):
        """截止期优先于相对超时：相对超时很长但截止期已过 → 判为过期."""
        node = EventNode(topic="t", content="c")
        node.set_timeout(10_000)
        node.set_deadline(time.monotonic() - 1)

        assert node.is_expire() is True

    def test_deadline_judgement_ignores_wall_clock(self, monkeypatch):
        """Scenario: 事件过期判定依据单调时钟而非墙钟."""
        real_time = time.time
        node = EventNode(topic="t", content="c")
        node.set_deadline(time.monotonic() - 1)

        monkeypatch.setattr(time, "time", lambda: real_time() - 31_536_000)
        assert node.is_expire() is True, "墙钟后跳让已过截止期的事件变成未过期"


class TestDispatchDeadline:
    """派发侧：一次派发 SHALL 可附带绝对截止期，超过时观测并熔断."""

    def test_dispatch_with_past_deadline_is_reaped(self):
        """Scenario: 派发侧超过截止期被观测并熔断."""
        core = WorkerDispatchCore()
        worker = _event_worker("D")
        core.set_workers([worker])

        assert core.begin(worker, None, deadline=time.monotonic() - 1) is not None
        assert core.reap_timeout(worker) is True
        assert core.is_broken(worker) is True
        assert core.metrics()["timeouts"] == 1

    def test_dispatch_with_future_deadline_is_not_reaped(self):
        core = WorkerDispatchCore()
        worker = _event_worker("D")

        core.begin(worker, None, deadline=time.monotonic() + 60)
        assert core.reap_timeout(worker) is False
        assert core.is_broken(worker) is False

    def test_broken_worker_leaves_the_dispatch_list(self):
        """Scenario: 熔断后不再无条件重派."""
        core = WorkerDispatchCore()
        worker = _event_worker("D")

        core.begin(worker, None, deadline=time.monotonic() - 1)
        core.reap_timeout(worker)
        core.set_workers([worker])

        assert core.retain_looping(core.workers) == [], "已熔断的 Worker 仍留在调度列表"

    def test_deadline_takes_priority_over_run_timeout(self):
        """给出了截止期时以截止期判定，不再看相对超时."""
        core = WorkerDispatchCore()
        worker = _event_worker("D")

        # 相对超时很远，但截止期已过 → 仍应熔断
        core.begin(worker, 9999, deadline=time.monotonic() - 1)
        assert core.reap_timeout(worker) is True
