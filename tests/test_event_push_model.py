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


def _queue_snapshot(channel):
    """按弹出顺序读出队列里剩余事件的 (topic, content)（只用于测试断言）."""
    items = []
    while True:
        node = channel.pop_value()
        if node is None:
            return items
        items.append((node.topic, node.content))


class TestConditionGating:
    def test_channel_created_with_condition_when_enabled(self, push_env):
        """启用推模型 → 通道持有 Condition."""
        manager, _ = push_env
        assert manager.get_channel("ch").condition is not None

    def test_channel_condition_is_none_when_disabled(self, pull_env):
        """关闭推模型 → 通道不创建 Condition（关闭零分配零分支）."""
        manager, _ = pull_env
        assert manager.get_channel("ch").condition is None

    def test_disabled_producer_path_is_noop(self, pull_env):
        """3.2 关闭零影响：生产路径不分配 Condition、不取锁（notify 是空操作）."""
        manager, _ = pull_env
        channel = manager.get_channel("ch")

        channel.notify_ready()  # 未启用：空操作
        channel.push_event(EventNode(topic="t", content="c", channel_name="ch"))

        assert channel.condition is None, "关闭态生产路径 MUST NOT 懒建 Condition"
        assert channel.size() == 1, "空操作不得影响入队本身"

    def test_condition_is_backfilled_when_switch_turns_on_late(self, pull_env):
        """通道在开关打开**之前**创建时，首读参数补建 Condition（不永久失聪）.

        运行期启用（config 之外）与热部署都走这条路径：通道对象不会重生，
        唤醒设施只能靠首个使用者补建。
        """
        manager, _ = pull_env
        channel = manager.get_channel("ch")
        assert channel.condition is None

        EventParams.PUSH_MODEL_ENABLED = True  # 运行期打开；fixture 负责恢复
        assert channel.wait_ready(0.01) is False, "空队列：兜底超时后返回 False"
        assert channel.condition is not None, "开关打开后首读 MUST 补建 Condition"

        # 补建出来的 Condition 必须真的可被唤醒（不是只建了个对象）——
        # 兜底拍远大于 1s，提前返回只可能是 notify 的功劳
        results = []
        elapsed = []

        def wait_and_time():
            t0 = time.perf_counter()
            woke = channel.wait_ready(3.0)
            elapsed.append(time.perf_counter() - t0)
            results.append(woke)

        waiter = threading.Thread(target=wait_and_time)
        waiter.start()
        time.sleep(0.05)  # 让 waiter 先挂起
        channel.push_event(EventNode(topic="t", content="c", channel_name="ch"))
        waiter.join(timeout=3.0)
        assert not waiter.is_alive(), "补建后入队 MUST 唤醒挂起的消费者"
        assert results == [True]
        assert elapsed[0] < 1.0, f"入队 MUST 立即唤醒而非等满兜底拍，实际 {elapsed[0]:.3f}s"


class TestNotifyWakesWait:
    def test_push_notify_wakes_wait(self, push_env):
        """生产者入队唤醒挂起消费者：wait 返回 True 且观察到队列非空."""
        manager, _ = push_env
        channel = manager.get_channel("ch")
        results = []
        elapsed = []

        def waiter():
            t0 = time.perf_counter()
            woke = channel.wait_ready(timeout=3.0)
            elapsed.append(time.perf_counter() - t0)
            # 调用时快照：唤醒后立即读 size，验证期不重读原对象
            results.append((woke, channel.size()))

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.05)  # 让 waiter 先挂起
        channel.push_event(EventNode(topic="t", content="c", channel_name="ch"))
        t.join(timeout=3.0)
        assert not t.is_alive(), "waiter 应被 notify 唤醒而非等满兜底拍"
        assert results == [(True, 1)]
        # 牙齿：兜底拍 3s；若 notify 被吞，wait 会等满 3s，此断言变红
        assert elapsed[0] < 1.0, f"入队到唤醒 MUST 远快于兜底拍，实际 {elapsed[0]:.3f}s"

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
        elapsed = []

        def waiter():
            t0 = time.perf_counter()
            results.append(channel.wait_ready(timeout=3.0))
            elapsed.append(time.perf_counter() - t0)

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.05)
        channel.dispatch("t", "c")
        t.join(timeout=3.0)
        assert not t.is_alive()
        assert results == [True]
        assert elapsed[0] < 1.0, f"dispatch MUST 唤醒而非等满兜底拍，实际 {elapsed[0]:.3f}s"


class TestWorkerSuspend:
    def test_worker_wakes_on_producer_event(self, push_env):
        """端到端：挂起中的 _execute 被生产者 notify 唤醒完成排空并投递."""
        manager, worker = push_env
        channel = manager.get_channel("default")
        sink = worker._test_sink
        EventParams.PUSH_FALLBACK_TIMEOUT = 3.0  # fixture 负责恢复
        producer = threading.Thread(
            target=lambda: (
                time.sleep(0.02),
                channel.push_event(EventNode(topic="t", content="c", channel_name="default")),
            )
        )
        producer.start()
        started = time.perf_counter()
        worker._execute()
        elapsed = time.perf_counter() - started
        producer.join()
        # 事件被投递（快照断言）、无死信：去向语义在推模型开启态下同样成立
        assert sink.calls == [("t", "c")]
        assert channel.get_dead_letters() == []
        # 牙齿：兜底拍 3s；若 notify 被吞，本轮会等满 3s 才返回，此断言变红
        assert elapsed < 1.0, f"入队 MUST 唤醒本轮排空而非等满兜底拍，实际 {elapsed:.3f}s"

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


class TestRequeueAlsoNotifies:
    """1.3：回队路径经同一生产入口，同样唤醒挂起的消费者（design D4）."""

    def test_requeue_path_also_notifies(self, push_env):
        """留额事件回队时也 notify——回队不是"静默塞回去"."""
        manager, _ = push_env
        channel = manager.get_channel("ch")
        node = EventNode(topic="t", content="c", channel_name="ch")
        node.set_retry_times(1)  # 留额 → 回队而非死信

        woke = []
        elapsed = []

        def waiter():
            t0 = time.perf_counter()
            woke.append(channel.wait_ready(3.0))
            elapsed.append(time.perf_counter() - t0)

        t = threading.Thread(target=waiter)
        t.start()
        time.sleep(0.05)  # 让 waiter 先挂起
        EventWorker._requeue_or_dead_letter(channel, node, reason="no matching reactor")
        t.join(timeout=3.0)

        assert not t.is_alive(), "回队 MUST 通知挂起的消费者"
        assert woke == [True]
        assert elapsed[0] < 1.0, f"回队 MUST 立即唤醒而非等满兜底拍，实际 {elapsed[0]:.3f}s"
        assert _queue_snapshot(channel) == [("t", "c")], "回队后事件应回到队列"
        assert node.get_retry_times() == 0, "回队路径必须递减重试次数"
        assert channel.get_dead_letters() == []


class TestFallbackResumesScan:
    """2.2 / scenario 兜底超时恢复扫描：生产者漏通知时事件不会无限期滞留."""

    def test_missed_notify_fallback_resumes_and_consumes(self, push_env):
        """绕过 notify 直接入队：消费者只能靠兜底拍醒来，且醒来后必须消费积压."""
        manager, worker = push_env
        channel = manager.get_channel("default")
        sink = worker._test_sink
        EventParams.PUSH_FALLBACK_TIMEOUT = 0.3  # 兜底拍；fixture 负责恢复

        done = threading.Event()
        consumer = threading.Thread(target=lambda: (worker._execute(), done.set()))
        consumer.start()
        time.sleep(0.1)  # 让消费者进入挂起（此刻队列为空）

        t0 = time.perf_counter()
        # 模拟「生产者侧异常漏通知」：直接入队，绕过 push_event 的 notify
        channel._event_fifo.push_value(EventNode(topic="t", content="c", channel_name="default"))
        assert done.wait(2.0), "兜底超时后消费者 MUST 恢复扫描，而不是永久挂起"
        elapsed = time.perf_counter() - t0
        consumer.join(timeout=2.0)

        assert elapsed >= 0.05, f"漏通知时不该被立即唤醒（那是 notify 的活），实际 {elapsed:.3f}s"
        assert elapsed < 2.0, f"恢复扫描不应晚于兜底拍太多，实际 {elapsed:.3f}s"
        assert sink.calls == [("t", "c")], "恢复扫描后积压事件 MUST 被消费"


def _run_outcomes(push_enabled: bool):
    """在指定开关态下跑一轮排空，返回三类去向的观测（投递 / 回队 / 死信）."""
    framework_container().reset()
    from zoo_framework.event.event_channel_register import EventChannelRegister

    EventChannelRegister._channel_map.clear()
    old_enabled = EventParams.PUSH_MODEL_ENABLED
    old_timeout = EventParams.PUSH_FALLBACK_TIMEOUT
    EventParams.PUSH_MODEL_ENABLED = push_enabled
    EventParams.PUSH_FALLBACK_TIMEOUT = 0.05
    try:
        worker = EventWorker()
        sink = _register_sink(worker)
        channel = worker.eventChannelManager.get_channel("default")

        deliverable = EventNode(topic="t", content="deliver", channel_name="default")
        retriable = EventNode(topic="nowhere", content="retry", channel_name="default")
        retriable.set_retry_times(1)  # 有留额 → 回队
        doomed = EventNode(topic="nowhere", content="dead", channel_name="default")
        doomed.set_retry_times(0)  # 无留额 → 死信
        for node in (deliverable, retriable, doomed):
            channel.push_event(node)

        worker._execute()
        return list(sink.calls), _queue_snapshot(channel), len(channel.get_dead_letters())
    finally:
        EventParams.PUSH_MODEL_ENABLED = old_enabled
        EventParams.PUSH_FALLBACK_TIMEOUT = old_timeout


class TestOutcomeParityAcrossSwitches:
    """3.1 语义守护：推模型开/关两态下事件去向逐项一致."""

    def test_outcomes_identical_with_push_on_and_off(self):
        """每个事件恰好投递/回队/死信三者之一，且开关两态结果完全相同."""
        with_push = _run_outcomes(push_enabled=True)
        without_push = _run_outcomes(push_enabled=False)

        assert with_push == without_push, f"两态去向不一致：{with_push} vs {without_push}"

        delivered, queued, dead = with_push
        assert delivered == [("t", "deliver")], "可投递事件恰好投递一次"
        assert queued == [("nowhere", "retry")], "留额事件恰好回队一次（且已递减重试）"
        assert dead == 1, "无留额事件恰好进死信"
        assert len(delivered) + len(queued) + dead == 3, "三个事件去向恰好其一"


class TestIdleSuspendEndToEnd:
    """4.1 端到端：空闲期挂起零扫描；入队即醒，延迟远小于心跳节拍."""

    def test_idle_suspends_without_scanning_then_wakes_quickly(self, push_env):
        """兜底拍拉到 3s：提前醒来只可能是 notify 的功劳，不是兜底轮询."""
        manager, worker = push_env
        channel = manager.get_channel("default")
        sink = worker._test_sink
        EventParams.PUSH_FALLBACK_TIMEOUT = 3.0  # fixture 负责恢复

        # 计数「扫描」（`channel.size()` 调用）：空闲挂起期间必须一次都不发生
        scans = []
        real_size = channel.size

        def counting_size():
            scans.append(1)
            return real_size()

        channel.size = counting_size

        done = threading.Event()
        consumer = threading.Thread(target=lambda: (worker._execute(), done.set()))
        consumer.start()
        time.sleep(0.3)  # 空闲窗口

        assert not done.is_set(), "空闲期 MUST 挂起等待，而不是空转返回"
        idle_scans = len(scans)
        time.sleep(0.2)
        assert len(scans) == idle_scans, f"空闲期不得扫描，实际新增 {len(scans) - idle_scans} 次"

        t0 = time.perf_counter()
        channel.push_event(EventNode(topic="t", content="c", channel_name="default"))
        assert done.wait(3.0), "生产者入队后 MUST 唤醒挂起的消费者"
        elapsed = time.perf_counter() - t0
        consumer.join(timeout=3.0)

        heartbeat = EventParams.EVENT_DELAY_TIME
        assert elapsed < heartbeat, (
            f"入队到消费的延迟 MUST 小于心跳间隔 {heartbeat}s，实际 {elapsed:.3f}s"
        )
        assert elapsed < 1.0, f"兜底拍 3s 未到即被唤醒才是 notify 生效的证据，实际 {elapsed:.3f}s"
        assert sink.calls == [("t", "c")], "被唤醒的这一轮必须完成排空投递"
