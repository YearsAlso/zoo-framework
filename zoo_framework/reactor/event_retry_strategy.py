from enum import Enum


class EventRetryStrategy(Enum):
    """事件重试策略."""

    RetryOnce = 0

    RetryAlways = 1

    RetryNever = 2

    RetryForever = 3

    RetryTimes = 4
