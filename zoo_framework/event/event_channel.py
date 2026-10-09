from threading import Condition

from zoo_framework.fifo import EventFIFO
from zoo_framework.fifo.node import EventNode
from zoo_framework.reactor import EventReactor, EventReactorManager
from zoo_framework.utils import LogUtils


class EventChannel:
    """事件通道.

    队列与响应器管理器都是**实例级**的：`EventChannel` 由 `EventChannelRegister`
    按名称创建并缓存，单例应当落在注册器（名称 → 通道的映射）上，而不是落在每个
    通道实例内部持有的队列上。曾经二者是类属性，导致所有通道共用一条队列。
    """

    # 死信记录上限，避免长期运行下无限增长
    _DEAD_LETTER_LIMIT = 1000

    def __init__(self, channel_name):
        # 事件队列（每个通道独立）
        self._event_fifo: EventFIFO = EventFIFO()

        # 事件反应器管理器（进程级注册，各通道持有同一引用；响应器登记仍是全局的）
        self._reactor_manager = EventReactorManager()

        # 无法投递的事件记录（死信）
        self._dead_letters: list = []

        # 是否公开, 通道不公开时, 只能通过事件反应器来触发事件,如果公开, 则可以通过事件通道来触发事件
        self.public = False
        # 通道名称
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
            True 表示被 notify 唤醒（队列可能非空）；False 表示超时或未启用
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
        """获取事件反应器."""
        return self._reactor_manager.get_reactor(topic)

    def get_channel_name(self):
        """获取通道名称."""
        return self.channel_name

    def set_public(self, public):
        """设置是否公开."""
        self.public = public

    def is_public(self):
        """是否公开."""
        return self.public

    def size(self):
        """获取事件队列大小."""
        return self._event_fifo.size()

    def pop_value(self) -> EventNode | None:
        """从事件队列中弹出事件."""
        return self._event_fifo.pop_value()

    def get_top(self) -> EventNode | None:
        """获取事件队列的第一个事件；队列为空时为 None."""
        return self._event_fifo.get_top()

    def push_event(self, event: EventNode):
        """将事件推入事件队列.

        推模型：入队成功后 notify 挂起的消费者；事件入队失败不通知（队列未变）。
        """
        try:
            self._event_fifo.push_value(event)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)
            return
        self._notify_ready()

    def dispatch(self, topic, content):
        """将事件推入事件队列（同 push_event 的推模型语义）."""
        self._event_fifo.dispatch(topic, content, self.channel_name)
        self._notify_ready()

    def register_reactor(self, topic, reactor):
        """注册事件反应器.

        同时记录该响应器监听的通道——通道的名称只有作为注册发起方的通道知道。
        此前只做了主题绑定而没有通道登记，导致 `@event(channel=...)` 声明的通道
        约束在分发热路径上完全不生效：通道管理器查不到登记，一律按默认通道放行。
        """
        self._reactor_manager.bind_topic_reactor(topic, reactor)
        self._reactor_manager.register_reactor_channels(reactor.reactor_name, [self.channel_name])

    def refresh_event(self, event):
        """刷新事件."""
        # 判断管道中是否存在该事件
        if self._event_fifo.has_event(event):  # 如果存在
            # 替换事件
            self._event_fifo.replace(event)

    def push_dead_letter(self, event, reason: str = "") -> None:
        """记录一个无法投递的事件.

        从队列取出的事件 MUST 有确定去向：被投递、被回队、或被记入本记录。
        MUST NOT 出现"取出后既未投递也未回队"的情况——那正是事件静默丢失的来源。

        Args:
            event: 未能投递的事件
            reason: 未能投递的原因，用于排查
        """
        LogUtils.error(
            f"事件进入死信 channel={self.channel_name} "
            f"topic={getattr(event, 'topic', None)} reason={reason}",
            EventChannel.__name__,
        )
        self._dead_letters.append(event)
        if len(self._dead_letters) > self._DEAD_LETTER_LIMIT:
            del self._dead_letters[: len(self._dead_letters) - self._DEAD_LETTER_LIMIT]

    def get_dead_letters(self) -> list:
        """获取当前通道的死信记录."""
        return list(self._dead_letters)
