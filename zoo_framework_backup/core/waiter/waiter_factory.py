"""
waiter_factory - zoo_framework/core/waiter/waiter_factory.py

模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""

waiter_factory - zoo_framework/core/waiter/waiter_factory.py

模块功能描述：

作者: XiangMeng

版本: 0.5.1-beta
"""

from .base_waiter import BaseWaiter
from .safe_waiter import SafeWaiter
from .simple_waiter import SimpleWaiter
from .stable_waiter import StableWaiter


class WaiterFactory:
    """WaiterFactory - 类功能描述"""
    @staticmethod
    def get_waiter(name="simple") -> BaseWaiter:
        if name == "simple":
            return SimpleWaiter()
        if name == "stable":
            return StableWaiter()
        if name == "safe":
            return SafeWaiter()
        return SimpleWaiter()
