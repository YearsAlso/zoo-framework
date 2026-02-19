"""
event_params - zoo_framework/params/event_params.py

模块功能描述:
TODO: 添加模块功能描述


    """EventParams - 类功能描述

    TODO: 添加类功能详细描述
    """
作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class EventParams:
    EVENT_JOIN_TIMEOUT = ParamsPath(value="event:timeout", default=5)
    EVENT_SLEEP_TIME = ParamsPath(value="event:sleep", default=0.2)
