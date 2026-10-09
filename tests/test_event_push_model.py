"""推模型（event-push-model）单元测试.

断言纪律：可变 EventNode 的断言只覆盖构造后不再变化的话题字段；调用录制用
list.append 调用时快照。

隔离：framework_container().reset() + EventChannelRegister._channel_map 清理
（conftest 三类同形态）。EventParams 已被 @params 烙上解析后字面值——测试内
直接改/恢复类属性即替身，restore 在 finally 里确定性完成（#51 陷阱的既有结论，
与 batching 测试同款手法）。
"""

import threading
import time

import pytest

from zoo_framework.core.container import framework_container
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.fifo.node import EventNode
from zoo_framework.params import EventParams
from zoo_framework.workers.event_worker import EventWorker


@pytest.fixture
def push_env():
    """启用推模型的干净环境；EventParams 类属性替身在用例后恢复."""
    framework_container().reset()
    from zoo_framework.event.event_channel_register import EventChannelRegister

    EventChannelRegister._channel_map.clear()
    worker = EventWorker()
    _register_sink(worker)
    old_enabled = EventParams.PUSH_MODEL_ENABLED
    old_timeout = EventParams.PUSH_FALLBACK_TIMEOUT
    EventParams.PUSH_MODEL_ENABLED = True
    EventParams.PUSH_FALLBACK_TIMEOUT = 0.05
    yield EventChannelManager(), worker
    EventParams.PUSH_MODEL_ENABLED = old_enabled
    EventParams.PUSH_FALLBACK_TIMEOUT = old_timeout


@pytest.fixture
def pull_env():
    """关闭推模型（默认态）的干净环境；类属性替身同样恢复."""
    framework_container().reset()
    from zoo_framework.event.event_channel_register import EventChannelRegister

    EventChannelRegister._channel_map.clear()
    worker = EventWorker()
    _register_sink(worker)
    old_enabled = EventParams.PUSH_MODEL_ENABLED
    old_timeout = EventParams.PUSH_FALLBACK_TIMEOUT
    EventParams.PUSH_MODEL_ENABLED = False
    EventParams.PUSH_FALLBACK_TIMEOUT = 0.05
    yield EventChannelManager(), worker
    EventParams.PUSH_MODEL_ENABLED = old_enabled
    EventParams.PUSH_FALLBACK_TIMEOUT = old_timeout


class _SinkReactor:
    """消费沉井：execute 时间调用快照（断言事件真被投递）.

    直接继承 EventReactor（bind_topic_reactor 会访问 set_event_timeout 等方法）
    并把 handle_callback 指到快照 append。
    """

    def __init__(self):
        from zoo_framework.reactor import EventReactor

        self._reactor = EventReactor("sink")
        self.calls = []
        self._reactor.set_event_callback(lambda req: self.calls.append((req.topic, req.content)))

    # EventWorker/管理器访问的响应器外观方法转发到内嵌真 EventReactor
    @property
    def reactor_name(self):
        return self._reactor.reactor_name

    def get_priority(self):
        return self._reactor.get_priority()

    def set_event_timeout(self, timeout):
        self._reactor.set_event_timeout(timeout)

    def execute(self, topic, content):
        self._reactor.execute(topic, content)


def _register_sink(worker):
    """给 worker 排空路径一个可命中的响应器."""
    channel = worker.eventChannelManager.get_channel("default")
    sink = _SinkReactor()
    channel.register_reactor("t", sink)
    worker._test_sink = sink
    return sink


class TestConditionGating:
    def test_channel_created_with_condition_when_enabled(self, push_env):
        """启用推模型 → 通道持有 Condition."""
        manager, _ = push_env
        assert manager.get_channel("ch").condition is not None

    def test_channel_condition_is_none_when_disabled(self, pull_env):
        """关闭推模型 → 通道不创建 Condition（关闭零分配零分支）."""
        manager, _ = pull_env
        assert manager.get_channel("ch").condition is None


class TestNotifyWakesWait:
    def test_push_notify_wakes_wait(self, push_env):
        """生产者入队唤醒挂起消费者：wait 返回 True 且观察到队列非空."""
        manager, _ = push_env
        channel = manager.get_channel("ch")
        results = []

        def waiter():
            woke = channel.wait_ready(timeout=2.0)
            # 调用时快照：唤醒后立即读 size，验证期不重读原对象
            results.append((woke, channel.size()))

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.05)  # 让 waiter 先挂起
        channel.push_event(EventNode(topic="t", content="c", channel_name="ch"))
        t.join(timeout=2.0)
        assert not t.is_alive(), "waiter 应被 notify 唤醒而非等满 2s"
        assert results == [(True, 1)]

    def test_wait_ready_returns_true_immediately_when_queue_nonempty(self, push_env):
        """队列已非空再 wait_ready：立即返回 True（通知前状态可见性，无丢失唤醒）."""
        manager, _ = push_env
        channel = manager.get_channel("ch")
        channel.push_event(EventNode(topic="t", content="c", channel_name="ch"))
        t0 = time.perf_counter()
        woke = channel.wait_ready(timeout=5.0)
        elapsed = time.perf_counter() - t0
        assert woke is True
        assert elapsed < 0.5, f"非空队列的 wait_ready 应立即返回，实际 {elapsed:.3f}s"

    def test_wait_ready_fallback_after_timeout(self, push_env):
        """生产者缺位 → 兜底超时后恢复返回 False（消费循环可继续）."""
        manager, _ = push_env
        channel = manager.get_channel("ch")
        t0 = time.perf_counter()
        woke = channel.wait_ready(timeout=0.05)
        elapsed = time.perf_counter() - t0
        assert woke is False
        assert elapsed >= 0.04, "应等满兜底超时而不是提前返回"

    def test_dispatch_also_notifies(self, push_env):
        """dispatch 生产路径同样触发通知."""
        manager, _ = push_env
        channel = manager.get_channel("ch")
        results = []

        def waiter():
            results.append(channel.wait_ready(timeout=2.0))

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.05)
        channel.dispatch("t", "c")
        t.join(timeout=2.0)
        assert not t.is_alive()
        assert results == [True]


class TestWorkerSuspend:
    def test_worker_wakes_on_producer_event(self, push_env):
        """端到端：挂起中的 _execute 被生产者 notify 唤醒完成排空并投递."""
        manager, worker = push_env
        channel = manager.get_channel("default")
        sink = worker._test_sink
        producer = threading.Thread(
            target=lambda: (
                time.sleep(0.02),
                channel.push_event(EventNode(topic="t", content="c", channel_name="default")),
            )
        )
        producer.start()
        worker._execute()
        producer.join()
        # 事件被投递（快照断言）、无死信：去向语义在推模型开启态下同样成立
        assert sink.calls == [("t", "c")]
        assert channel.get_dead_letters() == []

    def test_worker_all_empty_returns_quickly_after_fallback(self, push_env):
        """兜底超时且全空：本轮无事返回（无事件、无死信、不多扫）."""
        _, worker = push_env
        t0 = time.perf_counter()
        worker._execute()
        elapsed = time.perf_counter() - t0
        # 挂起兜底 0.05s 后全空返回（远小于心跳间隔 5s）
        assert elapsed < 1.0, f"兜底空扫应快速返回，实际 {elapsed:.2f}s"

    def test_disabled_worker_behaves_as_polling(self, pull_env):
        """关闭态 _execute：走既有逐事件路径，无推模型分支动作."""
        manager, worker = pull_env
        channel = manager.get_channel("default")
        sink = worker._test_sink
        for i in range(3):
            channel.push_event(EventNode(topic="t", content=f"c{i}", channel_name="default"))
        worker._execute()  # 推模型关闭：不挂起，直接排空
        assert len(sink.calls) == 3
        assert channel.get_dead_letters() == []
        # 生产者零开销：condition 恒 None（关闭零分配的可观测证据）
        assert channel.condition is None
