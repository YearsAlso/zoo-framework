"""
event_retry_strategy - zoo_framework/reactor/event_retry_strategy.py

模块功能描述.

作者: XiangMeng
版本: 0.5.2-beta
"""

event_retry_strategy - zoo_framework/reactor/event_retry_strategy.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta

from enum import Enum


class EventRetryStrategy(Enum):
    """事件重试策略."""

    RetryOnce = 0

    RetryAlways = 1

    RetryNever = 2

    RetryForever = 3

    RetryTimes = 4

""""""
