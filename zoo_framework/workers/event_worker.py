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
    """事件 Worker.

    消费循环的关键约束：从队列取出的事件 MUST 有确定去向——被投递、被回队、
    或被记入死信。静默丢弃是本类历史上最主要的事件丢失来源。

    注意：本类**不得**加任何"替换类"的装饰器（历史的 `@cage` 正是如此，已删除）。
    `WorkerRegistry.register_class` 用 `issubclass` 校验契约，把类换成函数就会让它抛
    `TypeError: issubclass() arg 1 must be a class`。单例与实例缓存由
    `WorkerRegistry._worker_instances` 承担，无需第二套机制——所以本类也不加
    `@process_scoped`：那会把"每 Worker 一实例"的归属从 `WorkerRegistry` 挪走。
    """

    def __init__(self):
        # EventParams 惰性导入且需先于 props 组装：节拍参与 BaseWorker.__init__。
        # 解析发生在首次导入、早于配置载入会冻结成默认值（见 #51）——本类由
        # WorkerRegistry 在运行期构造，该顺序成立。
        from zoo_framework.params import EventParams

        # is_loop 由 BaseWorker 以属性形式暴露、以 _props 为唯一真源；
        # 此处 MUST NOT 再用实例属性遮蔽它（属性无 setter，赋值会直接抛 AttributeError）。
        BaseWorker.__init__(
            self,
            {
                "is_loop": True,
                "delay_time": EventParams.EVENT_DELAY_TIME,
                "name": "EventWorker",
            },
        )

        # 事件处理器注册器
        self.eventChannelManager: EventChannelManager = EventChannelManager()

        # 响应器投递执行器：实例级建一次（align-execution-primitives D1）。
        # 替代历史的 gevent.spawn/joinall：greenlet 系原语在 free-threaded 构建上
        # 不可用，且实测单次派发 38.1 µs 远高于线程提交。
        self._executor = ThreadPoolExecutor(
            max_workers=EventParams.EVENT_EXECUTOR_WORKERS,
            thread_name_prefix="zoo-event-reactor",
        )
        # 销毁路径经 BaseWorker.__del__ 调用；wait=False 与 greenlet 时代一致：
        # 不做强杀也不无限等待在飞响应器。
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
        # TODO：获得除去失败事件通道的所有事件通道
        for channel_name in channel_names:
            # get_channel 的实现在未命中时会就地创建再返回，故它**不会**返回 None；
            # 原先那处 `if channel is None: continue` 因此是死分支（类型检查已证），已删。
            channel: EventChannel = self.eventChannelManager.get_channel(channel_name)
            # 获得所有的事件通道
            # 本轮只消费开始时就已在队列中的事件：回队的事件留到下一轮再处理，
            # 否则重试额度会在同一次消费循环里被瞬间耗尽，重试形同虚设。
            pending = channel.size()
            while pending > 0:
                pending -= 1
                event_node: EventNode | None = channel.pop_value()
                # size() 与 pop_value() 之间存在空档：并发生产者可能在此期间取走元素。
                # 取出为空表示本轮已无事件，必须结束循环——对 None 调用任何方法都会抛异常。
                if event_node is None:
                    break
                # 判断事件是否过期
                if event_node.is_expire():
                    event_node.expire_callback()
                    continue
                # 获得事件反应器
                try:
                    reactors = self.eventChannelManager.get_channel_reactors(event_node)
                except Exception as e:
                    # 事件已被取出，异常路径同样必须有确定去向
                    channel.push_dead_letter(event_node, reason=f"查询响应器失败: {e}")
                    continue
                # 如果这里为空，需要查看node 是否有重试次数，如果有重试次数，需要重新放入队列
                # `not reactors` 同时覆盖 None 与 []：get_channel_reactors 的返回类型是
                # `list[EventReactor] | None`，None 表示"没有匹配的响应器"，与空列表同义。
                # （此处原先写 len(reactors) == 0，靠 None 触发 TypeError 被上面的 except
                # 兜住——那是用异常做控制流，且把"无匹配"错报成"查询响应器失败"。）
                if not reactors:
                    self._requeue_or_dead_letter(channel, event_node, reason="没有匹配的响应器")
                    continue
                for reactor in reactors:
                    # 执行事件反应器：EventReactor 的公开入口是 execute(topic, content)。
                    f = self._executor.submit(reactor.execute, event_node.topic, event_node.content)
                    dispatched.append(f)

        if len(dispatched) > 0:
            # 有界等待本轮派发结果；超时项与异常项均转交可观测上报
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
        ——执行器簿记按批计而非按事件计（31.9µs/事件 → 31.9µs/批）。
        批内仍逐事件调用 execute(topic, content)，语义不变；批内异常捕获后
        打包为 BatchReactorError 上抛到 future，由批级上报携带事件定位信息。
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
            while pending > 0 and len(batches) < batch_limit:
                pending -= 1
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
        """事件未能投递时的确定去向.

        还有重试额度就递减并回队，否则记入死信——两条路径都可观测，不存在静默丢弃。

        Args:
            channel: 事件所属通道
            event_node: 未能投递的事件
            reason: 未能投递的原因
        """
        remaining = event_node.get_retry_times()
        if remaining > 0:
            event_node.set_retry_times(remaining - 1)
            channel.push_event(event_node)
            return

        channel.push_dead_letter(event_node, reason=reason)

    @staticmethod
    def _report_unfinished(dispatched: list[Future]) -> None:
        """上报 join 超时后仍在运行的响应器，并上报已结束的响应器抛出的异常.

        超时未结束者的结果不会被回收，MUST 可观测，而非随超时静默消失；
        已结束者携带的异常 MUST NOT 被吞掉（greenlet 时代它们静默消失）。

        Args:
            dispatched: 本轮派发的全部 future
        """
        unfinished = [f for f in dispatched if not f.done()]
        if unfinished:
            LogUtils.warning(
                f"{len(unfinished)} 个响应器在 join 超时后仍未结束，其结果未被回收",
                "EventWorker",
            )

        for f in dispatched:
            if not f.done():
                continue
            # done() 后取 exception() 不阻塞；未抛异常时为 None。
            exc = f.exception()
            if exc is not None:
                LogUtils.warning(f"响应器执行抛出异常且结果未被回收: {exc!r}", "EventWorker")
