from .base_waiter import BaseWaiter


class StableWaiter(BaseWaiter):
    """稳定调度器：资源池尺寸严格按配置，不自动扩容。"""

    def __init__(self):
        BaseWaiter.__init__(self)
