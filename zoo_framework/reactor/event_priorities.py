"""
event_priorities - zoo_framework/reactor/event_priorities.py

模块功能描述.

作者: XiangMeng
版本: 0.5.2-beta
"""

event_priorities - zoo_framework/reactor/event_priorities.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta

from enum import Enum


class EventPriorities(Enum):
    """Event priorities for the reactor."""

    # Lowest priority, executed first.
    LOWEST = 0

    # Low priority.
    LOW = 1

    # Normal priority.
    NORMAL = 2

    # High priority.
    HIGH = 3

    # Highest priority, executed last.
    HIGHEST = 4

    # Monitor priority, executed last.
    MONITOR = 5

""""""
