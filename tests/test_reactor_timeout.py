"""fix-reactor-timeout 专项测试（issue #232）.

覆盖三条规格场景：
- 超时/异常上报携带 reactor + topic 定位
- 声明了合法慢（event_timout 正值）的反应器豁免于「未完成」告警
- 未声明（0/负值/None）跟随全局默认，行为与本变更合入前一致

断言纪律（assertion-integrity）：告警以 side_effect-style 在调用现场录制成
不可变字符串快照，再对快照做断言——不引用可变对象。
"""

import time

import pytest

import zoo_framework.workers.event_worker as event_worker_module
from zoo_framework.core.aop.event import event
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.fifo.node.event_fifo_node import EventNode
from zoo_framework.params import EventParams
from zoo_framework.reactor.event_reactor import EventReactor
from zoo_framework.workers.event_worker import EventWorker


class _Capture:
    """录制告警快照：调用现场把 message 变成不可变 str."""

    def __init__(self):
        self.warnings: list[str] = []

    def warning(self, message, *_args, **_kwargs):
        self.warnings.append(str(message))


@pytest.fixture()
def capture(monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(event_worker_module, "LogUtils", cap)
    return cap


@pytest.fixture()
def probe_channel():
    """独立通道，注册表隔离由 conftest 的 reset 夹具承担。"""
    EventChannelManager().refresh_channel(
        "reactor-timeout-probe", "t.timeout", EventReactor("seed")
    )
    return EventChannelManager().get_channel("reactor-timeout-probe")


class TestDeclarationSemantics:
    """任务 1.3：声明语义（默认 0、@event 写入、非法值视为未声明）."""

    def test_default_is_undeclared(self):
        assert EventReactor("r").event_timout == 0

    def test_event_decorator_declares_timeout(self):
        @event("declared.topic", channel="reactor-timeout-probe", timeout=8)
        def handler(_req):
            pass

        reactor = (
            EventChannelManager()
            .get_channel("reactor-timeout-probe")
            .get_reactors("declared.topic")[0]
        )
        assert reactor.event_timout == 8

    def test_non_positive_and_none_collapse_to_undeclared(self):
        reactor = EventReactor("r")
        for value in (None, 0, -1):
            reactor.set_event_timeout(value)
            assert reactor.event_timout == 0


class TestEffectiveTimeout:
    """任务 2.1：两级解析."""

    def test_declared_wins(self):
        reactor = EventReactor("r")
        reactor.set_event_timeout(9)
        assert EventWorker._effective_timeout(reactor) == 9

    @pytest.mark.parametrize("declared", [0, None, -2])
    def test_undeclared_follows_global(self, monkeypatch, declared):
        monkeypatch.setattr(EventParams, "EVENT_JOIN_TIMEOUT", 3)
        reactor = EventReactor("r")
        reactor.event_timout = declared
        assert EventWorker._effective_timeout(reactor) == 3

    def test_no_stamp_at_registration(self):
        """bind_topic_reactor MUST NOT 以全局值盖章（未声明保持未声明）."""
        reactor = EventReactor("nostamp")
        EventChannelManager().refresh_channel("stamp-probe", "t.stamp", reactor)
        # 全局默认为 5；若注册盖章，字段会变成 5 而非 0
        assert reactor.event_timout == 0

    def test_no_stamp_at_registration_keeps_declaration(self):
        """注册盖章移除后，注册时机的旧声明不被抹掉."""
        reactor = EventReactor("keep")
        reactor.set_event_timeout(120)
        EventChannelManager().refresh_channel("stamp-probe-2", "t.stamp2", reactor)
        assert reactor.event_timout == 120


class TestWaitIsMaxEffective:
    """任务 2.2/2.3：等待时长 = max(生效超时)."""

    def test_undeclared_round_uses_global_default(self, probe_channel, monkeypatch, capture):
        """全部未声明时 wait = 全局默认，行为锚定（与合入前等价）."""
        monkeypatch.setattr(EventParams, "EVENT_JOIN_TIMEOUT", 0.05)
        # seed 反应器也让它慢一点但未声明：future 才有活，wait 才真的等满全局值
        seed = EventReactor("undeclared-slow")
        seed.set_event_callback(lambda _req: time.sleep(0.2))
        probe_channel.register_reactor("t.timeout", seed)
        probe_channel.push_event(EventNode(topic="t.timeout", content={"id": 1}))

        start = time.monotonic()
        EventWorker()._execute()
        # 未声明者按全局 0.05 上报——wait(0.05) 在 0.2s 工作完成前返回
        elapsed = time.monotonic() - start
        assert 0.04 <= elapsed < 0.35
        assert any("undeclared-slow" in w for w in capture.warnings), (
            f"未声明慢反应器应按全局值上报: {capture.warnings}"
        )

    def test_declared_max_extends_wait(self, probe_channel, monkeypatch, capture):
        """声明的最大生效值成为本轮等待时长."""
        monkeypatch.setattr(EventParams, "EVENT_JOIN_TIMEOUT", 0.05)

        # 未声明 + 慢（0.2s 工作量，全局 0.05 会提前超时）作对照：
        # 声明 0.3 的对照组必等满——证明 max 生效值驱动 wait
        reactor = EventReactor("lazy-declared")
        reactor.set_event_callback(lambda _req: time.sleep(0.2))
        reactor.set_event_timeout(0.3)
        probe_channel.register_reactor("t.timeout", reactor)
        probe_channel.push_event(EventNode(topic="t.timeout", content={"id": 1}))

        start = time.monotonic()
        EventWorker()._execute()
        # 工作本身 0.2s：若 wait 只取全局 0.05，会在工作完成后立刻返回并告警；
        # 取 max(0.3, 0.05)=0.3 时工作先完成、wait 不早于工作结束
        assert 0.19 <= time.monotonic() - start < 0.6
        assert capture.warnings == [], f"声明 0.3 的反应器不应被上报: {capture.warnings}"

    def test_declared_slow_reactor_not_reported(self, probe_channel, monkeypatch, capture):
        """规格场景：声明合法慢的反应器不触发告警，全局对其余继续生效."""
        monkeypatch.setattr(EventParams, "EVENT_JOIN_TIMEOUT", 0.05)

        slow = EventReactor("user-asked-slow")
        slow.set_event_callback(lambda _req: time.sleep(0.45))
        slow.set_event_timeout(1.0)
        probe_channel.register_reactor("t.timeout", slow)
        probe_channel.push_event(EventNode(topic="t.timeout", content={"id": "ui"}))

        EventWorker()._execute()
        assert capture.warnings == [], f"声明 1.0s 的反应器跑了 0.45s 仍告警: {capture.warnings}"


class TestLocatedReporting:
    """任务 3.3：上报携带定位."""

    def test_timeout_warning_carries_location(self, probe_channel, monkeypatch, capture):
        monkeypatch.setattr(EventParams, "EVENT_JOIN_TIMEOUT", 0.05)

        slow = EventReactor("located-slow")
        slow.set_event_callback(lambda _req: time.sleep(0.3))
        probe_channel.register_reactor("t.timeout", slow)
        probe_channel.push_event(EventNode(topic="t.timeout", content={"id": 1}))

        EventWorker()._execute()

        assert capture.warnings, "慢反应器越界必须上报"
        assert any("reactor=located-slow" in w and "t.timeout" in w for w in capture.warnings), (
            f"上报缺少定位: {capture.warnings}"
        )

    def test_exception_warning_carries_location(self, probe_channel, capture):
        reactor = EventReactor("located-raiser")

        def boom(_topic, _content):
            raise RuntimeError("boom")

        reactor.execute = boom
        probe_channel.register_reactor("t.timeout", reactor)
        probe_channel.push_event(EventNode(topic="t.timeout", content={"id": 1}))

        EventWorker()._execute()

        # 异常上报有牙齿：勇与定位一起断言——若实现改错（吞掉异常或丢定位），
        # 断言变红
        assert any(
            "reactor=located-raiser" in w and "t.timeout" in w and "RuntimeError" in w
            for w in capture.warnings
        ), f"异常上报缺少定位: {capture.warnings}"
