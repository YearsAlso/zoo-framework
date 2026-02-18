"""
waiter_result_reactor - zoo_framework/reactor/waiter_result_reactor.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
    """WaiterResultReactor - 类功能描述

    TODO: 添加类功能详细描述
    """
版本: 0.5.1-beta
"""

from zoo_framework.core.aop import cage

from .event_reactor import EventReactor


@cage
class WaiterResultReactor(EventReactor):
    def __init__(self):
        super().__init__("WaiterResultReactor")
        self._event_timeout = 0
