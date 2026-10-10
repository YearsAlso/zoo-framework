from concurrent.futures import Future, ThreadPoolExecutor, wait
from functools import partial
from typing import TYPE_CHECKING

from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker

if TYPE_CHECKING:
    from zoo_framework.event import EventChannel
    from zoo_framework.fifo.node import EventNode


class BatchReactorError(Exception):
    """一批内若干事件执行失败时携带批上下文与失败项定位的聚合异常.

    Attributes:
        items: 本批全部 (topic, content, node) 项（供上报还原批内顺序）
        failures: 失败项列表，每项为 (批内索引, 事件节点, 异常)
    """

    def __init__(self, items: list, failures: list):
        self.items = items
        self.failures = failures
        super().__init__(f"事件批内 {len(failures)}/{len(items)} 个事件执行失败")


class EventWorker(BaseWorker):
    """Event Worker.

    The key constraint of the consume loop: every event taken from the
    queue MUST have a settled destination - delivered, requeued, or moved to
    dead-letter. Silent dropping was historically this class's main source of
    event loss.

    Note: this class MUST NOT be decorated with any class-replacing decorator
    (the historical `@cage` did exactly that and was deleted).
    `WorkerRegistry.register_class` validates the contract with `issubclass`;
    swapping the class for a function would make it raise
    `TypeError: issubclass() arg 1 must be a class`. The singleton and the
    instance cache are owned by `WorkerRegistry._worker_instances`, with no
    second mechanism needed - so this class also does not take
    `@process_scoped`: that would move the "one instance per Worker"
    ownership away from `WorkerRegistry`.
    """

    def __init__(self):
        # EventParams is imported lazily and must precede the props assembly:
        # the tempo participates in BaseWorker.__init__.
        # Resolution happens at first import; freezing into the defaults
        # would occur if it were earlier than the config load (see #51) -
        # this class is constructed by WorkerRegistry at runtime, so the
        # order holds.
        from zoo_framework.params import EventParams

        # is_loop is exposed by BaseWorker as a property with _props as the
        # sole source of truth; here it MUST NOT be shadowed by an instance
        # attribute (the property has no setter, assignment raises
        # AttributeError directly).
        BaseWorker.__init__(
            self,
            {
                "is_loop": True,
                "delay_time": EventParams.EVENT_DELAY_TIME,
                "name": "EventWorker",
            },
        )

        # Event channel manager
        self.eventChannelManager: EventChannelManager = EventChannelManager()

        # Reactor dispatch executor: built once per instance
        # (align-execution-primitives D1). Replaces the historical
        # gevent.spawn/joinall: greenlet primitives are unavailable on
        # free-threaded builds, and a single dispatch measured 38.1 us, far
        # above a thread submit.
        self._executor = ThreadPoolExecutor(
            max_workers=EventParams.EVENT_EXECUTOR_WORKERS,
            thread_name_prefix="zoo-event-reactor",
        )
        # The destroy path is invoked via BaseWorker.__del__; wait=False
        # matches the greenlet era: no forced kill and no unbounded wait for
        # in-flight reactors.
        self._destroy_func = partial(self._executor.shutdown, wait=False, cancel_futures=True)

    def _execute(self):
        from zoo_framework.params import EventParams

        # 推模型（add-event-push-model）：若无事件，挂起等待生产者 notify——
        # 被唤醒或兜底超时后进入下方正常排空，消费主体完全复用。
        # 关闭时 _push_wait 是零开销空操作，行为与合入前逐字节一致。
        # 注意 MUST NOT 在挂起后做「全空则跳过排空」的守卫：notify/超时与
        # 生产者入队之间没有原子性，守卫求值瞬间恰好入队的事件会被饿到
        # 下一拍——空排空只花 µs，而竞态丢的可是真事件。
        if EventParams.PUSH_MODEL_ENABLED:
            self._push_wait(EventParams.PUSH_FALLBACK_TIMEOUT)

        if EventParams.DISPATCH_BATCHING_ENABLED:
            self._execute_batched()
            return

        channel_names = self.eventChannelManager.get_all_channel_name()
        dispatched: list[Future] = []
        # TODO: get all event channels except failed ones
        for channel_name in channel_names:
            # get_channel creates-and-returns in place on a miss, so it will **never** return None;
            # the old `if channel is None: continue` was therefore dead code (proven by type checking) and was removed.
            channel: EventChannel = self.eventChannelManager.get_channel(channel_name)
            # Get all the event channels
            # This round only consumes events already queued at round start: requeued events wait for the next round,
            # otherwise the retry quota is exhausted within one consume loop and retrying is void.
            pending = channel.size()
            while pending > 0:
                pending -= 1
                event_node: EventNode | None = channel.pop_value()
                # A race window exists between size() and pop_value(): a concurrent producer may take elements in between.
                # An empty pop means no events this round; the loop must end - any method call on None raises.
                if event_node is None:
                    break
                # Decide whether the event is expired
                if event_node.is_expire():
                    event_node.expire_callback()
                    continue
                # Get the event reactors
                try:
                    reactors = self.eventChannelManager.get_channel_reactors(event_node)
                except Exception as e:
                    # The event was already popped; the exception path also needs a settled destination
                    channel.push_dead_letter(event_node, reason=f"failed to look up reactors: {e}")
                    continue
                # If empty here, check the node's retry quota; with quota left it must go back to the queue.
                # `not reactors` covers both None and []: get_channel_reactors returns
                # `list[EventReactor] | None`, where None means "no matching reactor", same as an
                # empty list. (This used to be written len(reactors) == 0, with a None-triggered
                # TypeError caught by the except above - exceptions as control flow, misreporting
                # "no match" as "failed to look up reactors".)
                if not reactors:
                    self._requeue_or_dead_letter(channel, event_node, reason="no matching reactor")
                    continue
                for reactor in reactors:
                    # Run the event reactor: EventReactor's public entry is execute(topic, content).
                    f = self._executor.submit(reactor.execute, event_node.topic, event_node.content)
                    dispatched.append(f)

        if len(dispatched) > 0:
            # A bounded wait for this round's dispatch results; timeouts and exceptions both go to observable reporting
            wait(dispatched, timeout=EventParams.EVENT_JOIN_TIMEOUT)
            self._report_unfinished(dispatched)

    def _push_wait(self, timeout: float) -> None:
        """推模型挂起：在所有通道的 Condition 上等待有事件（design D3）.

        依次对每个通道 wait_ready：任一通道被唤醒即返回（消费主体下一行立即
        排空）；每通道各自的兜底超时防止生产者侧异常导致的永久滞留。
        通道无 Condition（推模型关闭）时 wait_ready 立即返回，零开销。
        """
        for name in self.eventChannelManager.get_all_channel_name():
            channel = self.eventChannelManager.get_channel(name)
            if channel.wait_ready(timeout) and channel.size() > 0:
                return

    def _execute_batched(self):
        """批量投递的消费排空（optimize-event-dispatch-batching D1/D2）.

        与逐事件路径相同的排空骨架（批量扫描/去向语义/重试），仅投递段不同：
        同 (channel, reactor) 的待投递事件聚合为一批，以单个 callable 一次提交
        ——执行器簿记按批计而非按事件计（本变更 4.1 同一运行内实测：逐事件提交
        5.8µs/事件 → 批上限 64 时摊到 0.17µs/事件；读数与口径见变更目录的
        booking_measurement.json）。
        批内仍逐事件调用 execute(topic, content)，语义不变；批内异常捕获后
        打包为 BatchReactorError 上抛到 future，由批级上报携带事件定位信息。

        批大小上限（design D2）：**限量的是取，不是裁**——本轮从每个通道最多
        取出 `event:batchMaxSize` 个事件，超出的留在队列里按原顺序等下一轮。
        每个批相应不超过该上限，大批独占执行器线程的形态被此上限兜住。
        """
        from zoo_framework.params import EventParams

        channel_names = self.eventChannelManager.get_all_channel_name()
        dispatched: list[Future] = []
        batch_limit = EventParams.BATCH_MAX_SIZE
        for channel_name in channel_names:
            channel: EventChannel = self.eventChannelManager.get_channel(channel_name)
            pending = channel.size()
            # 聚合表：id(reactor) -> (reactor, [(topic, content, node), ...])
            batches: dict[int, tuple] = {}
            # 本轮从本通道取出的事件数（含过期/死信/回队者）——批上限的计量单位。
            # 计数放在 `pending -= 1` 之前（design D2 的"限量扫描"）：到上限就不再
            # pop，剩余事件**原样留在队列**里（不裁批、不丢失、不死信、不改顺序）。
            taken = 0
            while pending > 0 and taken < batch_limit:
                pending -= 1
                taken += 1
                event_node = channel.pop_value()
                if event_node is None:
                    break
                if event_node.is_expire():
                    event_node.expire_callback()
                    continue
                try:
                    reactors = self.eventChannelManager.get_channel_reactors(event_node)
                except Exception as e:
                    channel.push_dead_letter(event_node, reason=f"查询响应器失败: {e}")
                    continue
                if not reactors:
                    self._requeue_or_dead_letter(channel, event_node, reason="没有匹配的响应器")
                    continue
                for reactor in reactors:
                    key = id(reactor)
                    entry = batches.get(key)
                    if entry is None:
                        entry = batches[key] = (reactor, [])
                    entry[1].append((event_node.topic, event_node.content, event_node))
            # 每批一次 submit：一个 callable 消费整批
            for reactor, items in batches.values():
                f = self._executor.submit(self._run_batch, reactor, items)
                dispatched.append(f)

        if len(dispatched) > 0:
            wait(dispatched, timeout=EventParams.EVENT_JOIN_TIMEOUT)
            self._report_unfinished_batched(dispatched)

    @staticmethod
    def _run_batch(reactor, items) -> None:
        """执行一批（同 reactor 的多个事件）：逐事件 execute，异常聚合上抛.

        批内单事件异常不中断批内剩余事件（与既有逐事件提交语义一致——
        executor future 中 reactor 的异常本来就静默到 exception()）；
        已处理游标随 BatchReactorError 上抛，供批级上报定位到事件。
        """
        failures = []
        for index, (topic, content, node) in enumerate(items):
            try:
                reactor.execute(topic, content)
            except Exception as e:
                failures.append((index, node, e))
        if failures:
            raise BatchReactorError(items, failures)

    @staticmethod
    def _report_unfinished_batched(dispatched: list[Future]) -> None:
        """批级可观测（optimize-event-dispatch-batching D3）.

        未完成批数量上报（channel/reactor/批内事件数尽力给出——future 未完成时
        其 callable 已不可再读，故以批为单位计数）；已结束批携带的
        BatchReactorError 展开为带批内索引与事件 topic 的定位上报。
        """
        unfinished = [f for f in dispatched if not f.done()]
        if unfinished:
            LogUtils.warning(
                f"{len(unfinished)} 个响应器批在 join 超时后仍未结束，其结果未被回收",
                "EventWorker",
            )

        for f in dispatched:
            if not f.done():
                continue
            exc = f.exception()
            if exc is None:
                continue
            if isinstance(exc, BatchReactorError):
                for index, node, cause in exc.failures:
                    LogUtils.warning(
                        f"批内事件处理抛出异常 index={index} "
                        f"topic={getattr(node, 'topic', None)}: {cause!r}",
                        "EventWorker",
                    )
            else:
                LogUtils.warning(f"事件批执行抛出异常且结果未被回收: {exc!r}", "EventWorker")

    @staticmethod
    def _requeue_or_dead_letter(channel, event_node, reason: str = "") -> None:
        """The settled destination when an event cannot be delivered.

        With retry quota left, decrement it and requeue; otherwise move to
        dead-letter - both paths are observable, no silent dropping.

        Args:
            channel: the channel the event belongs to
            event_node: the event that could not be delivered
            reason: the reason it could not be delivered
        """
        remaining = event_node.get_retry_times()
        if remaining > 0:
            event_node.set_retry_times(remaining - 1)
            channel.push_event(event_node)
            return

        channel.push_dead_letter(event_node, reason=reason)

    @staticmethod
    def _report_unfinished(dispatched: list[Future]) -> None:
        """Report reactors still running past the join timeout, and exceptions carried by finished reactors.

        The results of ones unfinished at timeout are not collected and MUST
        be observable, not silently vanish with the timeout; exceptions
        carried by finished ones MUST NOT be swallowed (in the greenlet era
        they vanished silently).

        Args:
            dispatched: all futures dispatched in this round
        """
        unfinished = [f for f in dispatched if not f.done()]
        if unfinished:
            LogUtils.warning(
                f"{len(unfinished)} reactors were still running after the join timeout; their results were not collected",
                "EventWorker",
            )

        for f in dispatched:
            if not f.done():
                continue
            # After done(), exception() does not block; None when no exception was raised.
            exc = f.exception()
            if exc is not None:
                LogUtils.warning(
                    f"a reactor raised and its result was not collected: {exc!r}", "EventWorker"
                )
