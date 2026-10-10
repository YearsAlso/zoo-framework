import time
from collections.abc import Callable
from enum import Enum
from typing import Any

from zoo_framework.core.run_identity import current_identity


class PriorityLevel(Enum):
    """Priority level.

    P2 optimization: define standard priority levels.
    """

    CRITICAL = 1000  # critical/urgent
    HIGH = 500  # high priority
    NORMAL = 100  # normal
    LOW = 10  # low priority
    BACKGROUND = 1  # background task


class EventPriorityCalculator:
    """Event priority calculator.

    P2 optimization: implement a weighted priority algorithm to prevent priority inversion.
    """

    @staticmethod
    def calculate(
        priority: int,
        create_time: float,
        wait_time_weight: float = 0.3,
        max_wait_time: float = 300.0,  # 5分钟
    ) -> float:
        """Compute the combined priority score.

        Algorithm: combined priority = base priority + wait-time bonus.

        The wait-time bonus grows with elapsed time, preventing low-priority
        tasks from starving.

        Args:
            priority: the base priority
            create_time: the creation instant (on the **monotonic clock**
                basis, see ``EventNode.create_time``)
            wait_time_weight: the wait-time weight (0-1)
            max_wait_time: the maximum wait time in seconds

        Returns:
            The combined priority score (higher wins)
        """
        current_time = time.monotonic()
        wait_time = max(0, current_time - create_time)

        # 计算等待时间加成（指数增长，但不超过 max_wait_time）
        # 使用指数函数让等待时间的影响逐渐增大
        effective_wait = min(wait_time, max_wait_time)
        wait_bonus = effective_wait * (1 + effective_wait / max_wait_time) * wait_time_weight

        # 综合优先级 = 基础优先级 + 等待加成
        return priority + wait_bonus

    @staticmethod
    def get_urgency_level(priority: int) -> str:
        """Describe the urgency level for a priority.

        Args:
            priority: the priority value

        Returns:
            The urgency description
        """
        if priority >= PriorityLevel.CRITICAL.value:
            return "critical"
        if priority >= PriorityLevel.HIGH.value:
            return "high"
        if priority >= PriorityLevel.NORMAL.value:
            return "normal"
        if priority >= PriorityLevel.LOW.value:
            return "low"
        return "background"


class EventNode:
    """Event node - P2 optimized version.

    Optimizations:
    1. improved the priority computation algorithm
    2. added an anti-priority-inversion mechanism
    3. added the priority level enum
    """

    # 事件主题
    topic: str
    # 事件参数
    content: str
    # 响应次数
    retry_times: int
    # 响应机制，1.先抢到的先响应; 2.者优先级高的先响应; 3.全部响应; 4.指定响应者响应
    response_mechanism: int = 3
    # 制定响应者名称
    reactor_name: str | None = None
    # 是否响应完成
    is_response: bool = False
    # 执行优先级
    priority: int = 0
    # 事件通道名称
    channel_name: str = "default"
    # 超时时间
    timeout: int = 0
    # 超时响应
    timeout_response: Callable[..., Any] | None = None
    # 绝对截止期（**单调时钟**基准）；None 表示不按截止期判定过期。
    # 与 `timeout` 的区别：`timeout` 是"创建后允许存活多久"的区间量，
    # `deadline` 是"最迟必须在此刻之前处理"的绝对时刻。二者同基准，不得混入墙钟。
    deadline: float | None = None
    # 产生该事件的那次运行的标识；入队时从当前上下文盖章，可由生产方显式覆盖
    run_id: str | None = None
    # 该事件所属会话的标识
    session_id: str | None = None
    # 创建时间
    create_time: float
    # 失败响应
    fail_response: Callable[..., Any] | None = None

    def __init__(
        self,
        topic: str,
        content: str,
        channel_name: str = "default",
        priority: int = 0,
        priority_level: PriorityLevel | None = None,
    ):
        """Initialize the event node.

        P2 optimization: supports setting the priority via a PriorityLevel.

        Args:
            topic: the event topic
            content: the event content
            channel_name: the channel name
            priority: the priority value
            priority_level: the priority level (optional; takes precedence
                over the priority argument)
        """
        self.topic = topic
        self.content = content
        self.retry_times = 0

        # P2 优化：支持使用 PriorityLevel
        if priority_level is not None:
            self.priority = priority_level.value
        else:
            self.priority = priority

        self.channel_name = channel_name
        # 创建时刻取**单调时钟**：它只用于计算"等待了多久"与"是否超时"这类区间量，
        # 用墙钟会因 NTP 校时/夏令时跳变而算出负的等待时间或误判超时。
        self.create_time = time.monotonic()
        self.deadline = None
        # 运行标识在**入队时**盖章：显式字段是真相来源，接收方据此可按运行筛选事件，
        # 不依赖隐式上下文（事件会被跨线程消费，那里的上下文未必是生产方的）
        identity = current_identity()
        self.run_id = identity.run_id if identity is not None else None
        self.session_id = identity.session_id if identity is not None else None

    def __repr__(self) -> str:
        """:return: str"""
        return f"EventNode(topic={self.topic}, content={self.content}, priority={self.priority})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, EventNode):
            return False
        return self.topic == other.topic and self.content == other.content

    def __hash__(self) -> int:
        return hash((self.topic, self.content))

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other) -> bool:
        """Less-than comparison - used for sorting.

        P2 optimization: supports direct comparison, for the priority queue.
        """
        if not isinstance(other, EventNode):
            return NotImplemented
        return self.get_effective_priority() < other.get_effective_priority()

    def __gt__(self, other) -> bool:
        """Greater-than comparison - used for sorting."""
        if not isinstance(other, EventNode):
            return NotImplemented
        return self.get_effective_priority() > other.get_effective_priority()

    def __index__(self) -> int:
        """Return the priority index.

        P2 optimization: uses the weighted priority algorithm.
        """
        return int(self.get_effective_priority())

    def get_effective_priority(self) -> float:
        """Get the effective priority.

        P2 optimization: computed via PriorityCalculator.

        Returns:
            The effective priority score
        """
        return EventPriorityCalculator.calculate(
            priority=self.priority,
            create_time=self.create_time,
            wait_time_weight=0.3,
            max_wait_time=300.0,
        )

    def get_urgency(self) -> str:
        """Get the urgency description.

        Returns:
            The urgency string
        """
        return EventPriorityCalculator.get_urgency_level(self.priority)

    def set_fail_response(self, fail_response: Callable[..., Any]):
        """Set the failure response."""
        self.fail_response = fail_response

    def set_reactor_name(self, reactor_name: str):
        """Set the reactor name."""
        self.reactor_name = reactor_name

    def set_response_mechanism(self, response_mechanism: int, reactor_name: str | None = None):
        """Set the response mechanism."""
        self.response_mechanism = response_mechanism
        if response_mechanism == 4:
            if reactor_name is None:
                raise ValueError("reactor name must not be empty when response_mechanism is 4")
            self.reactor_name = reactor_name

    def get_topic(self) -> str:
        """Get the event topic."""
        return self.topic

    def get_content(self) -> str:
        """Get the event content."""
        return self.content

    def set_timeout(self, timeout: int, timeout_response: Callable[..., Any] | None = None):
        """Set the timeout."""
        self.timeout = timeout
        self.timeout_response = timeout_response

    def set_deadline(self, deadline: float | None):
        """Set the absolute deadline.

        Args:
            deadline: the absolute instant (**monotonic clock** basis); None
                cancels the deadline
        """
        self.deadline = deadline

    def set_identity(self, run_id: str | None, session_id: str | None = None) -> None:
        """Set the run identity explicitly.

        Overrides the values stamped from the context at enqueue time, for
        producers acting outside a run context.

        Args:
            run_id: the run identity
            session_id: the session identity
        """
        self.run_id = run_id
        self.session_id = session_id

    def is_expire(self) -> bool:
        """Whether the node is expired.

        **The deadline takes precedence over the relative timeout**: given a
        ``deadline``, it decides; otherwise the interval between ``timeout``
        and the creation instant decides. Both share the ``create_time`` basis
        (monotonic clock) and MUST NOT mix in the wall clock.
        """
        now = time.monotonic()

        if self.deadline is not None:
            return now >= self.deadline

        if self.timeout is None or self.timeout == 0:
            return False

        return 0 < self.timeout < (now - self.create_time)

    def expire_callback(self):
        """Expire callback."""
        if self.timeout_response is not None:
            self.timeout_response(self)

    def get_retry_times(self) -> int:
        """Get the remaining retry count."""
        return self.retry_times

    def set_retry_times(self, retry_times: int) -> None:
        """Set the remaining retry count.

        The consume path decides from this whether an undeliverable event
        requeues for retry or is moved to dead-letter.

        Args:
            retry_times: the remaining retry count; <=0 means no more retries
        """
        self.retry_times = max(0, int(retry_times))

    def increment_retry(self) -> None:
        """Increment the retry count.

        Added in P2: increments the retry count automatically.
        """
        self.retry_times += 1


# 导出公共 API
__all__ = [
    "EventNode",
    "EventPriorityCalculator",
    "PriorityLevel",
]
