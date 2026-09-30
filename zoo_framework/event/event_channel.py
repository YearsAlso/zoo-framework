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

    def get_top(self) -> EventNode:
        """获取事件队列的第一个事件."""
        return self._event_fifo.get_top()

    def push_event(self, event: EventNode):
        """将事件推入事件队列."""
        try:
            self._event_fifo.push_value(event)
        except Exception as e:
            LogUtils.error(str(e), EventFIFO.__name__)

    def dispatch(self, topic, content):
        """将事件推入事件队列."""
        self._event_fifo.dispatch(topic, content, self.channel_name)

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
