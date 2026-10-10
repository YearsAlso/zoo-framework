"""批量投递（optimize-event-dispatch-batching）单元测试.

断言纪律（assertion-integrity）：EventNode 是会被就地改写的可变对象（重试递减等），
涉及「调用携带内容」的断言一律用调用时快照或在构造时绑定不可变量（topic/content
为写入后不再变化的字段——事件构造后立即入队消费，属 assertion-integrity 例外
条款「对象在构造后不再被改写」……但重试路径会改其 retry 字段，故凡断言重试
语义仍用快照登记）。ToListReactor 用 list.append 快照每次调用的实参。

隔离：EventChannelManager 是 process_scoped 单例——每个用例用框架容器 reset +
manager._reactor_channels/_channels 清理（与 conftest 三类载体同形态）。
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import zoo_framework.workers.event_worker as ew_mod
from zoo_framework.core.container import framework_container
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.fifo.node import EventNode
from zoo_framework.reactor import EventReactor
from zoo_framework.workers.event_worker import BatchReactorError, EventWorker


def _fresh_manager():
    """干净容器 + 返回进程级 manager 单例（EventChannelManager() 即单例访问）."""
    framework_container().reset()
    # 清理通道注册的类级缓存（conftest 三类载体中的通道配置面）
    from zoo_framework.event.event_channel_register import EventChannelRegister

    EventChannelRegister._channel_map.clear()
    return EventChannelManager()


class RecordingReactor(EventReactor):
    """录制每次 execute(topic, content) 调用时的实参快照."""

    def __init__(self, name):
        self._name = name
        self.calls = []

    @property
    def reactor_name(self):
        return self._name

    def execute(self, topic, content):
        # 调用时快照：record 即拷贝实参，验证期读到的必然是调用时的值
        self.calls.append((topic, content))


class FailingSomeReactor(RecordingReactor):
    """对特定 topic 抛异常、其余录制的响应器."""

    def __init__(self, name, fail_topic):
        super().__init__(name)
        self._fail_topic = fail_topic

    def execute(self, topic, content):
        if topic == self._fail_topic:
            raise ValueError(f"boom:{topic}")
        self.calls.append((topic, content))


class TestBatchSubmission:
    def test_batched_events_require_one_submit_per_reactor(self):
        """同 reactor 的多个事件一次提交：submit 调用次数 = 批数而非事件数."""
        manager = _fresh_manager()
        channel = manager.get_channel("ch")
        reactor = RecordingReactor("r")
        channel.register_reactor("t", reactor)
        # 注册响应器后 manager 需要 refresh 才能查到（manager 侧结构）

        worker = EventWorker()
        # 直接灌 1 个事件（manager.get_channel_reactors 依赖 manager 内登记）
        for _i in range(5):
            channel.push_event(EventNode(topic="t", content=f"c{_i}", channel_name="ch"))

        class CountingExecutor:
            """替身执行器：记录 submit 次数，同步执行"""

            def __init__(self):
                self.count = 0

            def submit(self, fn, *args):
                self.count += 1
                return _sync_future(fn, args)

        fake = CountingExecutor()
        worker._executor = fake
        worker._execute_batched()
        # 5 个事件同 reactor → 1 批 → 恰好 1 次 submit（若逐事件则为 5）
        assert fake.count == 1, f"批量路径应以 1 次提交投递 5 个事件，实际 {fake.count}"

    def test_batch_executes_each_event_in_order(self):
        """批内仍逐事件 execute(topic, content)，顺序与弹出顺序一致."""
        manager = _fresh_manager()
        channel = manager.get_channel("ch")
        reactor = RecordingReactor("r")
        channel.register_reactor("t", reactor)
        for i in range(4):
            channel.push_event(EventNode(topic="t", content=f"c{i}", channel_name="ch"))

        worker = EventWorker()
        # 真实语义：同步替身执行器
        worker._executor = _SyncExecutor()
        worker._execute_batched()

        assert len(reactor.calls) == 4
        assert reactor.calls == [("t", f"c{i}") for i in range(4)]

    def test_multiple_reactors_get_one_submit_each(self):
        """两个 reactor 各命中 3 个事件 → 2 批 2 次 submit，各批内含自己那组."""
        manager = _fresh_manager()

        class ChRouter:
            """topic 四六开到两个 reactor 的守卫（EventReactorManager 语义按名匹配）"""

            def get_reactor(self, topic):
                return [self._r1, self._r2]

        manager.get_channel("ch")

        r1 = RecordingReactor("r1")
        r2 = RecordingReactor("r2")
        ch = manager.get_channel("ch")
        ch.register_reactor("a", r1)
        ch.register_reactor("a", r2)

        for i in range(3):
            ch.push_event(EventNode(topic="a", content=f"c{i}", channel_name="ch"))

        worker = EventWorker()
        counted = _CountingSyncExecutor()
        worker._executor = counted
        worker._execute_batched()

        assert counted.count == 2, f"两个 reactor 应为 2 批，实际 {counted.count}"
        assert len(r1.calls) == 3 and len(r2.calls) == 3


class TestBatchOverflowAndFallback:
    def test_batch_size_cap_leaves_overflow_queued_in_order(self, monkeypatch):
        """批大小上限：本轮最多取上限个事件，溢出原样留队、顺序不变、不死信.

        牙齿：断言"第一轮恰好投递上限个、队列剩 7 个且头部是被取走事件的下一
        个"。若上限被写成"小组数上限"（不计已取事件数），第一轮会把 10 个全投
        出去 —— reactor.calls 与 ch.size() 两条断言同时变红。
        """
        from zoo_framework.params import EventParams

        monkeypatch.setattr(EventParams, "BATCH_MAX_SIZE", 3)
        manager = _fresh_manager()
        ch = manager.get_channel("ch")
        reactor = RecordingReactor("r")
        ch.register_reactor("t", reactor)
        for i in range(10):
            ch.push_event(EventNode(topic="t", content=f"c{i}", channel_name="ch"))

        worker = EventWorker()
        worker._executor = _SyncExecutor()
        worker._execute_batched()

        # 第一轮：上限 3 → 恰好投递 c0..c2，批大小不超过上限
        assert reactor.calls == [("t", f"c{i}") for i in range(3)]
        # 溢出事件留队：不被死信、不丢失，且头部仍是未被取走的 c3（顺序不变）
        assert ch.size() == 7
        assert ch.get_top().content == "c3"
        assert ch.get_dead_letters() == []

        # 后续轮次把剩余事件消费完（每轮同样受上限约束）：全部事件恰好投递一次
        rounds = 0
        while ch.size() > 0:
            rounds += 1
            assert rounds <= 4, "批次上限下应在有限轮内排空"
            worker._execute_batched()
        assert reactor.calls == [("t", f"c{i}") for i in range(10)]
        assert ch.get_dead_letters() == []

    def test_disabled_batching_uses_per_event_path(self):
        """开关关闭 → 走逐事件路径：submit 次数 = 事件数."""
        manager = _fresh_manager()
        ch = manager.get_channel("ch")
        reactor = RecordingReactor("r")
        ch.register_reactor("t", reactor)
        for i in range(3):
            ch.push_event(EventNode(topic="t", content=f"c{i}", channel_name="ch"))

        worker = EventWorker()
        counted = _CountingSyncExecutor()
        worker._executor = counted
        worker._execute()  # 未开启开关 → 逐事件

        assert counted.count == 3


class TestBatchObservability:
    def test_batch_exception_reported_with_event_locator(self):
        """批内异常上报带批内索引与 topic 定位，其余事件结果不被掩盖."""
        manager = _fresh_manager()
        ch = manager.get_channel("ch")
        reactor = FailingSomeReactor("r", fail_topic="bad")
        for t in ("ok1", "bad", "ok2"):
            ch.register_reactor(t, reactor)
        for t in ("ok1", "bad", "ok2"):
            ch.push_event(EventNode(topic=t, content=f"c-{t}", channel_name="ch"))

        worker = EventWorker()
        worker._executor = _SyncExecutor()

        warnings = []

        class GrabLogger:
            @staticmethod
            def warning(msg, *_args):
                warnings.append(msg)

        orig = ew_mod.LogUtils
        ew_mod.LogUtils = GrabLogger
        try:
            worker._execute_batched()
        finally:
            ew_mod.LogUtils = orig

        # ok 事件结果不被 bad 异常掩盖
        assert ("ok1", "c-ok1") in reactor.calls and ("ok2", "c-ok2") in reactor.calls
        # 上报包含 bad 事件的定位信息
        thrown = [w for w in warnings if "bad" in w and "ValueError" in w]
        assert thrown, f"应有携带 topic=bad 定位的异常上报，实际 {warnings}"
        # 批内 index=1（ok1 之后）
        assert any("index=1" in w for w in thrown), f"上报应含批内 index，实际 {thrown}"

    def test_batch_reactor_error_carries_items_and_failures(self):
        """BatchReactorError 结构可还原批内顺序与失败位置."""
        nodes = [EventNode(topic=f"t{i}", content=f"c{i}") for i in range(3)]
        items = [(n.topic, n.content, n) for n in nodes]
        err = BatchReactorError(items, [(1, nodes[1], ValueError("x"))])
        assert err.failures[0][0] == 1
        assert err.failures[0][1] is nodes[1]
        assert "1/3" in str(err)


class TestBatchConcurrency:
    def test_concurrent_reactors_snapshot_not_reference(self):
        """并发下的批内顺序快照：不同 reactor 的 item 各自归组（id 聚合正确性）."""
        manager = _fresh_manager()
        ch = manager.get_channel("ch")
        r1 = RecordingReactor("r1")
        r2 = RecordingReactor("r2")
        ch.register_reactor("a", r1)
        ch.register_reactor("b", r2)

        topics = ["a", "b"] * 4
        for i, t in enumerate(topics):
            ch.push_event(EventNode(topic=t, content=f"c{i}", channel_name="ch"))

        worker = EventWorker()
        worker._executor = _SyncExecutor()
        worker._execute_batched()

        # 快照断言：r1 恰好记录 4 个 topic=a，r2 恰好 4 个 topic=b（交错不串组）
        assert all(t == "a" for t, _ in r1.calls) and len(r1.calls) == 4
        assert all(t == "b" for t, _ in r2.calls) and len(r2.calls) == 4


# ---------------------------------------------------------------------------
# 测试设施（同步替身执行器；返回真 Future 以复用 _report_unfinished_batched 路径）
# ---------------------------------------------------------------------------


class _SyncExecutor:
    def submit(self, fn, *args):
        return _sync_future(fn, args)


class _CountingSyncExecutor(_SyncExecutor):
    def __init__(self):
        self.count = 0

    def submit(self, fn, *args):
        self.count += 1
        return super().submit(fn, *args)


def _sync_future(fn, args):
    """同步执行 fn 并包真 Future（供 wait()/_report_unfinished_batched 判定）."""
    from concurrent.futures import Future

    f: Future = Future()
    try:
        fn(*args)
    except Exception as e:
        f.set_exception(e)
    else:
        f.set_result(None)
    f.cancel()  # 已完成后的 cancel 是 False 返回，无副作用；防止误判仍在运行
    return f


# ThreadPoolExecutor 被 EventWorker.__init__ 引用（实例级建一次）；
# 测试里替换 _executor 属性即不依赖真线程池，此 import 保住引用不被误删。
_ = ThreadPoolExecutor
_ = threading.Condition
