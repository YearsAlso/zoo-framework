"""issue #230：FIFO 只保证「投递顺序」，完成顺序 MUST NOT 被当成 FIFO 承诺.

**先判断（本变更的结论）**：FIFO 的**完成顺序不是**框架承诺的语义。事件通道的
FIFO 承诺的是**出队/投递顺序**——``EventWorker`` 按队列顺序弹出事件并提交；而消费
侧的执行原语是共享线程池（``event:executor:workers``，默认 8），同一反应器的多次
调用会**重叠执行**，完成顺序由各次执行的实际结束时刻决定，与入队顺序无关。既然
从未承诺过，这里就不是行为缺陷，缺陷在于"未文档化的惊喜"：真实的顺序保证必须
写进规格与类说明。

本文件把真实的顺序保证变成可执行断言：

1. 通道 FIFO 的出队顺序 = 入队顺序（**这是**承诺的部分）；
2. 缺省（逐事件）路径下完成顺序由实际完成时刻决定，与入队顺序无关；
3. 批量投递把同 (channel, reactor) 同轮事件串行执行，故其完成顺序 = 出队顺序
   （这是"要顺序"的唯一现成开关，且是进程级开关）；
4. ``EventWorker`` 的类说明 MUST 写明该语义（文档项不可回退）。
"""

import time

import pytest

from zoo_framework.core.container import framework_container
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.fifo.node import EventNode
from zoo_framework.params import EventParams
from zoo_framework.reactor import EventReactor
from zoo_framework.workers.event_worker import EventWorker


def _fresh_manager():
    """干净容器 + 进程级 manager 单例（与批量投递用例同一隔离形态）。"""
    framework_container().reset()
    from zoo_framework.event.event_channel_register import EventChannelRegister

    EventChannelRegister._channel_map.clear()
    return EventChannelManager()


class CompletionOrderReactor(EventReactor):
    """按事件内容睡眠，睡完记录 id —— 把"并发"暴露成可观测的完成顺序。"""

    def __init__(self, name, durations):
        self._name = name
        self._durations = durations
        self.done: list[str] = []

    @property
    def reactor_name(self):
        return self._name

    def execute(self, topic, content):
        time.sleep(self._durations[content])
        self.done.append(content)


def _worker_with_real_executor():
    worker = EventWorker()
    return worker


def _shutdown(worker):
    worker._executor.shutdown(wait=True)


class TestDequeueOrderIsThePromise:
    def test_channel_dequeues_in_enqueue_order(self):
        """Scenario: 通道 FIFO 的出队顺序 = 入队顺序（承诺的部分）。"""
        manager = _fresh_manager()
        channel = manager.get_channel("ch")
        for i in range(5):
            channel.push_event(EventNode(topic="t", content=f"c{i}", channel_name="ch"))

        popped = [channel.pop_value().content for _ in range(5)]

        assert popped == [f"c{i}" for i in range(5)]


class TestCompletionOrderIsNotFifo:
    def test_completion_order_follows_completion_not_enqueue_order(self):
        """缺省路径：入队 A、B，A 慢 B 快 → 完成顺序为 B、A（非 FIFO）。"""
        manager = _fresh_manager()
        channel = manager.get_channel("ch")
        reactor = CompletionOrderReactor("probe-order", {"A": 0.4, "B": 0.01})
        channel.register_reactor("probe_topic", reactor)
        # 入队顺序：A 先、B 后
        channel.push_event(EventNode(topic="probe_topic", content="A", channel_name="ch"))
        channel.push_event(EventNode(topic="probe_topic", content="B", channel_name="ch"))

        worker = _worker_with_real_executor()
        try:
            worker._execute()
        finally:
            _shutdown(worker)

        assert reactor.done == ["B", "A"], (
            f"完成顺序应为实际完成顺序（B 先），而不是入队顺序（A 先），实际 {reactor.done}"
        )

    def test_batching_serializes_same_reactor_events_in_dequeue_order(self):
        """批量投递：同反应器同轮事件串行执行，完成顺序 = 出队顺序。"""
        manager = _fresh_manager()
        channel = manager.get_channel("ch")
        reactor = CompletionOrderReactor("probe-batch", {"A": 0.2, "B": 0.01})
        channel.register_reactor("probe_topic", reactor)
        channel.push_event(EventNode(topic="probe_topic", content="A", channel_name="ch"))
        channel.push_event(EventNode(topic="probe_topic", content="B", channel_name="ch"))

        worker = _worker_with_real_executor()
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(EventParams, "DISPATCH_BATCHING_ENABLED", True)
        try:
            worker._execute_batched()
        finally:
            monkeypatch.undo()
            _shutdown(worker)

        assert reactor.done == ["A", "B"], (
            f"批内串行执行，完成顺序应为出队顺序（A 先），实际 {reactor.done}"
        )


class TestOrderingIsDocumented:
    def test_event_worker_documents_delivery_not_completion_order(self):
        """EventWorker 类说明 MUST 写明：FIFO 只保证投递顺序，不保证完成顺序。"""
        doc = EventWorker.__doc__ or ""

        assert "delivery" in doc and "completion order" in doc, (
            "EventWorker 的类说明未写明顺序保证（issue #230 的未文档化惊喜）"
        )
