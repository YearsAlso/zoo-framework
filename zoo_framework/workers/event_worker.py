from concurrent.futures import Future, ThreadPoolExecutor, wait
from functools import partial
from typing import TYPE_CHECKING

from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker

if TYPE_CHECKING:
    from zoo_framework.event import EventChannel
    from zoo_framework.fifo.node import EventNode


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
        # is_loop 由 BaseWorker 以属性形式暴露、以 _props 为唯一真源；
        # 此处 MUST NOT 再用实例属性遮蔽它（属性无 setter，赋值会直接抛 AttributeError）。
        BaseWorker.__init__(self, {"is_loop": True, "delay_time": 5, "name": "EventWorker"})

        # 事件处理器注册器
        self.eventChannelManager: EventChannelManager = EventChannelManager()

        # 响应器投递执行器：实例级建一次（align-execution-primitives D1）。
        # 替代历史的 gevent.spawn/joinall：greenlet 系原语在 free-threaded 构建上
        # 不可用，且实测单次派发 38.1 µs 远高于线程提交。EventParams 仍须**惰性导入**
        # （解析发生在首次导入，早于配置载入会冻结成默认值，见 #51）——本类由
        # WorkerRegistry 在运行期构造，此处与 _execute 内的导入都满足该顺序。
        from zoo_framework.params import EventParams

        self._executor = ThreadPoolExecutor(
            max_workers=EventParams.EVENT_EXECUTOR_WORKERS,
            thread_name_prefix="zoo-event-reactor",
        )
        # 销毁路径经 BaseWorker.__del__ 调用；wait=False 与 greenlet 时代一致：
        # 不做强杀也不无限等待在飞响应器。
        self._destroy_func = partial(self._executor.shutdown, wait=False, cancel_futures=True)

    def _execute(self):
        from zoo_framework.params import EventParams

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
