"""configurable-run-delay（#73）：管道节拍参数化的回归测试.

缺陷形态：EventWorker 与 StateMachineWorker 的 ``delay_time`` 硬编码 5，
每一次事件派发都要等下一个节拍且无法调节；同时 ``event:sleep`` 是"声明了
却零消费"的死键——用户填了没有任何效果。本文件锁住三件事：配置入口真实
生效、默认值向后兼容、死键不再存在。
"""

from zoo_framework.params import EventParams, StateMachineParams
from zoo_framework.workers import EventWorker, StateMachineWorker


class TestEventDelayConfigurable:
    def test_default_keeps_historical_five_seconds(self):
        """默认节拍 5：与历史硬编码一致，行为向后兼容."""
        assert EventParams.EVENT_DELAY_TIME == 5
        assert StateMachineParams.STATE_MACHINE_DELAY_TIME == 5

    def test_event_worker_honors_event_delay(self, monkeypatch):
        """event:delay 必须进入 EventWorker 的调度节拍（此前钉死在 5）."""
        monkeypatch.setattr(EventParams, "EVENT_DELAY_TIME", 1)
        worker = EventWorker()
        try:
            assert worker.delay_time == 1
        finally:
            worker._destroy_func()  # 显式回收 executor，不等 __del__

    def test_state_machine_worker_honors_state_machine_delay(self, monkeypatch):
        """stateMachine:delay 必须进入 StateMachineWorker 的落盘周期."""
        monkeypatch.setattr(StateMachineParams, "STATE_MACHINE_DELAY_TIME", 2)
        worker = StateMachineWorker()
        assert worker.delay_time == 2


class TestDeadKeyRemoved:
    def test_event_sleep_key_no_longer_declared(self):
        """event:sleep 随 gevent 消费循环删除后零消费——已移除，不再"看起来可调"."""
        assert not hasattr(EventParams, "EVENT_SLEEP_TIME")
        declared = [getattr(p, "value", "") for p in vars(EventParams).values()]
        assert "event:sleep" not in declared
