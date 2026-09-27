from typing import TYPE_CHECKING

import gevent

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

    注意：本类**不得**加 `@cage`。`@cage` 会把类替换成工厂函数，而
    `WorkerRegistry.register_class` 用 `issubclass` 校验契约，二者不兼容
    （会抛 `TypeError: issubclass() arg 1 must be a class`）。单例与实例
    缓存由 `WorkerRegistry._worker_instances` 承担，无需第二套机制。
    """

    def __init__(self):
        # is_loop 由 BaseWorker 以属性形式暴露、以 _props 为唯一真源；
        # 此处 MUST NOT 再用实例属性遮蔽它（属性无 setter，赋值会直接抛 AttributeError）。
        BaseWorker.__init__(self, {"is_loop": True, "delay_time": 5, "name": "EventWorker"})

        # 事件处理器注册器
        self.eventChannelManager: EventChannelManager = EventChannelManager()

    def _execute(self):
        from zoo_framework.params import EventParams

        channel_names = self.eventChannelManager.get_all_channel_name()
        g_queue = []
        # TODO：获得除去失败事件通道的所有事件通道
        for channel_name in channel_names:
            channel: EventChannel = self.eventChannelManager.get_channel(channel_name)
            if channel is None:
                continue
            # 获得所有的事件通道
            # 本轮只消费开始时就已在队列中的事件：回队的事件留到下一轮再处理，
            # 否则重试额度会在同一次消费循环里被瞬间耗尽，重试形同虚设。
            pending = channel.size()
            while pending > 0:
                pending -= 1
                event_node: EventNode = channel.pop_value()
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
                if len(reactors) == 0:
                    self._requeue_or_dead_letter(channel, event_node, reason="没有匹配的响应器")
                    continue
                for reactor in reactors:
                    # 执行事件反应器：EventReactor 的公开入口是 execute(topic, content)。
                    g = gevent.spawn(reactor.execute, event_node.topic, event_node.content)
                    g_queue.append(g)

        if len(g_queue) > 0:
            # 执行处理方法
            gevent.joinall(g_queue, timeout=EventParams.EVENT_JOIN_TIMEOUT)
            self._report_unfinished(g_queue)

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
    def _report_unfinished(g_queue: list) -> None:
        """上报 join 超时后仍在运行的响应器.

        这些响应器的结果不会被回收，MUST 可观测，而非随 join 超时静默消失。

        Args:
            g_queue: 本轮派发的全部 greenlet
        """
        unfinished = [g for g in g_queue if not g.ready()]
        if unfinished:
            LogUtils.warning(
                f"{len(unfinished)} 个响应器在 join 超时后仍未结束，其结果未被回收",
                "EventWorker",
            )
