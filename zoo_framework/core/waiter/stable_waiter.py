from .base_waiter import BaseWaiter


class StableWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
