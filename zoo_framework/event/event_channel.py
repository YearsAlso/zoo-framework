from threading import Condition

from zoo_framework.fifo import EventFIFO
from zoo_framework.fifo.node import EventNode
from zoo_framework.reactor import EventReactor, EventReactorManager
from zoo_framework.utils import LogUtils


class EventChannel:
    """Event channel.

    The queue and the reactor manager are both **instance-level**:
    `EventChannel` is created and cached by name in `EventChannelRegister`;
    the singleton belongs on the registrar (the name -> channel map), not on
    the queue each channel instance holds inside itself. Both used to be
    class attributes, making all channels share one queue.
    """

    # Dead-letter record cap, to avoid unbounded growth over long runs
    _DEAD_LETTER_LIMIT = 1000

    def __init__(self, channel_name):
        # The event queue (independent per channel)
        self._event_fifo: EventFIFO = EventFIFO()

        # The event reactor manager (process-level registration; every channel
        # holds the same reference; reactor registration is still global)
        self._reactor_manager = EventReactorManager()

        # Records of undeliverable events (dead letters)
        self._dead_letters: list = []

        # Whether public: a non-public channel can only trigger events via
        # reactors; if public, events can be triggered via the channel itself
        self.public = False
        # The channel name
        self.channel_name = channel_name

        # 推模型唤醒设施（add-event-push-model D1/D2）：per-channel Condition，
        # 懒创建 + 开关门控——关闭时本属性恒 None，生产者路径零新增分支开销。
        from zoo_framework.params import EventParams

        self._condition: Condition | None = Condition() if EventParams.PUSH_MODEL_ENABLED else None

    # ---------------------------------------------------------------- 推模型

    @property
    def condition(self) -> Condition | None:
        """通道的推模型唤醒条件变量；未启用推模型时为 None."""
        return self._condition

    def _ensure_condition(self) -> Condition | None:
        """取唤醒条件变量；推模型未启用时返回 None.

        懒建兜底：通道可能在推模型开关打开**之前**创建（config 之外的运行期
        启用、测试替身、热部署）——此时首读参数决定是否补建，避免通道永久
        错过推模型。启用后不再回收（进程语义单向，回到关闭态由重建通道承担）。
        """
        if self._condition is None:
            from zoo_framework.params import EventParams

            if EventParams.PUSH_MODEL_ENABLED:
                self._condition = Condition()
        return self._condition

    def wait_ready(self, timeout: float) -> bool:
        """消费者挂起等待本通道有事件（推模型启用时）.

        Args:
            timeout: 兜底超时（秒）；超时后调用方恢复扫描（防生产者漏 notify）

        Returns:
            True 表示本次调用观察到队列非空（进入时已非空，或被 notify 唤醒）；
            False 表示等满兜底超时后仍空，或推模型未启用
        """
        condition = self._ensure_condition()
        if condition is None:
            return False
        with condition:
            if self._event_fifo.size() > 0:
                return True
            condition.wait(timeout)
            return self._event_fifo.size() > 0

    def notify_ready(self) -> None:
        """生产者通知：入队成功后唤醒挂起的消费者（推模型启用时）."""
        condition = self._ensure_condition()
        if condition is None:
            return
        with condition:
            condition.notify_all()

    # 兼容别名：生产者挂点统一走 notify_ready 明名语义
    _notify_ready = notify_ready

    def get_reactors(self, topic: str) -> list[EventReactor]:
        """Get the event reactors."""
        return self._reactor_manager.get_reactor(topic)

    def get_channel_name(self):
        """Get the channel name."""
        return self.channel_name

    def set_public(self, public):
        """Set whether the channel is public."""
        self.public = public

    def is_public(self):
        """Whether the channel is public."""
        return self.public

    def size(self):
        """Get the size of the event queue."""
        return self._event_fifo.size()

    def pop_value(self) -> EventNode | None:
        """Pop an event from the event queue."""
        return self._event_fifo.pop_value()

    def get_top(self) -> EventNode | None:
        """Get the first event of the event queue; None when the queue is empty."""
        return self._event_fifo.get_top()

    def push_event(self, event: EventNode):
        """Push an event into the event queue.

        Push model: notify suspended consumers after a successful enqueue;
        a failed enqueue does not notify (the queue did not change).
        """
        try:
            self._event_fifo.push_value(event)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)
            return
        self._notify_ready()

    def dispatch(self, topic, content):
        """Push an event into the event queue (same push-model semantics as `push_event`)."""
        self._event_fifo.dispatch(topic, content, self.channel_name)
        self._notify_ready()

    def register_reactor(self, topic, reactor):
        """Register an event reactor.

        Also records the channels the reactor listens to - only the channel
        initiating the registration knows the channel's name. Previously only
        the topic binding was done without the channel registration, so the
        channel constraint declared by `@event(channel=...)` did not apply at
        all on the dispatch hot path: the channel manager found no
        registration and let everything through on the default channel.
        """
        self._reactor_manager.bind_topic_reactor(topic, reactor)
        self._reactor_manager.register_reactor_channels(reactor.reactor_name, [self.channel_name])

    def refresh_event(self, event):
        """Refresh an event."""
        # Decide whether the event already exists in the pipeline
        if self._event_fifo.has_event(event):  # if it exists
            # Replace the event
            self._event_fifo.replace(event)

    def push_dead_letter(self, event, reason: str = "") -> None:
        """Record an event that cannot be delivered.

        An event taken from the queue MUST have a settled destination:
        delivered, requeued, or recorded here. "Popped and neither delivered
        nor requeued" MUST NOT happen - that is exactly how events get lost
        silently.

        Args:
            event: the event that could not be delivered
            reason: the reason it could not be delivered, for troubleshooting
        """
        LogUtils.error(
            f"event moved to dead-letter channel={self.channel_name} "
            f"topic={getattr(event, 'topic', None)} reason={reason}",
            EventChannel.__name__,
        )
        self._dead_letters.append(event)
        if len(self._dead_letters) > self._DEAD_LETTER_LIMIT:
            del self._dead_letters[: len(self._dead_letters) - self._DEAD_LETTER_LIMIT]

    def get_dead_letters(self) -> list:
        """Get the current channel's dead-letter records."""
        return list(self._dead_letters)
