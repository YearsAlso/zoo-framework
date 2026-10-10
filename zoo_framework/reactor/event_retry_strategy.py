from enum import Enum


class EventRetryStrategy(Enum):
    """The event retry strategy."""

    RetryOnce = 0

    RetryAlways = 1

    RetryNever = 2

    RetryForever = 3

    RetryTimes = 4
