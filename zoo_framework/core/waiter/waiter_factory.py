from .simple_waiter import SimpleWaiter
from .safe_waiter import SafeWaiter
from .stable_waiter import StableWaiter
from .base_waiter import BaseWaiter


class WaiterFactory:
    @staticmethod
    def get_waiter(name="simple") -> BaseWaiter:
        if name == "simple":
            return SimpleWaiter()
        elif name == "stable":
            return StableWaiter()
        elif name == "safe":
            return SafeWaiter()
        else:
            return SimpleWaiter()
