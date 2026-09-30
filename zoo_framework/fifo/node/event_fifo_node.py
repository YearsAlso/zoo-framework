import time
from collections.abc import Callable
from enum import Enum
from typing import Any

from zoo_framework.core.run_identity import current_identity


class PriorityLevel(Enum):
    """优先级等级.

    P2 优化：定义标准优先级等级
    """

    CRITICAL = 1000  # 关键/紧急
    HIGH = 500  # 高优先级
    NORMAL = 100  # 正常
    LOW = 10  # 低优先级
    BACKGROUND = 1  # 后台任务


class EventPriorityCalculator:
    """事件优先级计算器.

    P2 优化：实现加权优先级算法，防止优先级反转
    """

    @staticmethod
    def calculate(
        priority: int,
        create_time: float,
        wait_time_weight: float = 0.3,
        max_wait_time: float = 300.0,  # 5分钟
    ) -> float:
        """计算综合优先级分数.

        算法：综合优先级 = 基础优先级 + 等待时间加成

        等待时间加成会随时间增加而提高，防止低优先级任务饿死

        Args:
            priority: 基础优先级
            create_time: 创建时刻（**单调时钟**基准，见 ``EventNode.create_time``）
            wait_time_weight: 等待时间权重 (0-1)
            max_wait_time: 最大等待时间（秒）

        Returns:
            综合优先级分数（越高越优先）
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
        """根据优先级获取紧急程度描述.

        Args:
            priority: 优先级值

        Returns:
            紧急程度描述
        """
        if priority >= PriorityLevel.CRITICAL.value:
            return "🔴 紧急"
        if priority >= PriorityLevel.HIGH.value:
            return "🟠 高"
        if priority >= PriorityLevel.NORMAL.value:
            return "🟡 中"
        if priority >= PriorityLevel.LOW.value:
            return "🟢 低"
        return "⚪ 后台"


class EventNode:
    """事件节点 - P2 优化版本.

    优化内容：
    1. 改进优先级计算算法
    2. 添加防止优先级反转机制
    3. 添加优先级等级枚举
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
        """初始化事件节点.

        P2 优化：支持使用 PriorityLevel 设置优先级

        Args:
            topic: 事件主题
            content: 事件内容
            channel_name: 通道名称
            priority: 优先级数值
            priority_level: 优先级等级（可选，优先级高于 priority 参数）
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
        """小于比较 - 用于排序.

        P2 优化：支持直接比较，用于优先队列
        """
        if not isinstance(other, EventNode):
            return NotImplemented
        return self.get_effective_priority() < other.get_effective_priority()

    def __gt__(self, other) -> bool:
        """大于比较 - 用于排序."""
        if not isinstance(other, EventNode):
            return NotImplemented
        return self.get_effective_priority() > other.get_effective_priority()

    def __index__(self) -> int:
        """返回优先级索引.

        P2 优化：使用加权优先级算法
        """
        return int(self.get_effective_priority())

    def get_effective_priority(self) -> float:
        """获取有效优先级.

        P2 优化：使用 PriorityCalculator 计算

        Returns:
            有效优先级分数
        """
        return EventPriorityCalculator.calculate(
            priority=self.priority,
            create_time=self.create_time,
            wait_time_weight=0.3,
            max_wait_time=300.0,
        )

    def get_urgency(self) -> str:
        """获取紧急程度描述.

        Returns:
            紧急程度字符串
        """
        return EventPriorityCalculator.get_urgency_level(self.priority)

    def set_fail_response(self, fail_response: Callable[..., Any]):
        """设置失败响应."""
        self.fail_response = fail_response

    def set_reactor_name(self, reactor_name: str):
        """设置响应者名称."""
        self.reactor_name = reactor_name

    def set_response_mechanism(self, response_mechanism: int, reactor_name: str | None = None):
        """设置响应机制."""
        self.response_mechanism = response_mechanism
        if response_mechanism == 4:
            if reactor_name is None:
                raise ValueError("响应机制为4时，响应者名称不能为空")
            self.reactor_name = reactor_name

    def get_topic(self) -> str:
        """获取事件主题."""
        return self.topic

    def get_content(self) -> str:
        """获取事件参数."""
        return self.content

    def set_timeout(self, timeout: int, timeout_response: Callable[..., Any] | None = None):
        """设置超时时间."""
        self.timeout = timeout
        self.timeout_response = timeout_response

    def set_deadline(self, deadline: float | None):
        """设置绝对截止期.

        Args:
            deadline: 绝对时刻（**单调时钟**基准）；None 表示取消截止期
        """
        self.deadline = deadline

    def set_identity(self, run_id: str | None, session_id: str | None = None) -> None:
        """显式设置运行标识.

        覆盖入队时从上下文盖章的值，供不在运行上下文内的生产方显式标注。

        Args:
            run_id: 运行标识
            session_id: 会话标识
        """
        self.run_id = run_id
        self.session_id = session_id

    def is_expire(self) -> bool:
        """是否过期.

        **截止期优先于相对超时**：给出 ``deadline`` 时以它判定；否则按 ``timeout``
        与创建时刻的间隔判定。二者与 ``create_time`` 同基准（单调时钟），
        MUST NOT 混入墙钟。
        """
        now = time.monotonic()

        if self.deadline is not None:
            return now >= self.deadline

        if self.timeout is None or self.timeout == 0:
            return False

        return 0 < self.timeout < (now - self.create_time)

    def expire_callback(self):
        """过期回调."""
        if self.timeout_response is not None:
            self.timeout_response(self)

    def get_retry_times(self) -> int:
        """获取剩余重试次数."""
        return self.retry_times

    def set_retry_times(self, retry_times: int) -> None:
        """设置剩余重试次数.

        消费路径据此决定事件在无法投递时是回队重试还是记入死信。

        Args:
            retry_times: 剩余重试次数；<=0 表示不再重试
        """
        self.retry_times = max(0, int(retry_times))

    def increment_retry(self) -> None:
        """增加重试次数.

        P2 新增：自动增加重试次数
        """
        self.retry_times += 1


# 导出公共 API
__all__ = [
    "EventNode",
    "EventPriorityCalculator",
    "PriorityLevel",
]
