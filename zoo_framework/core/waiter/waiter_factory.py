from .base_waiter import BaseWaiter
from .safe_waiter import SafeWaiter
from .simple_waiter import SimpleWaiter
from .stable_waiter import StableWaiter


class WaiterFactory:
    @staticmethod
    def get_waiter(name="simple") -> BaseWaiter:
        if name == "simple":
            return SimpleWaiter()
        if name == "stable":
            return StableWaiter()
        if name == "safe":
            return SafeWaiter()
        return SimpleWaiter()
