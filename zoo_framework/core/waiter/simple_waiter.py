from .base_waiter import BaseWaiter


class SimpleWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)

    # 集结worker们
    def call_workers(self, worker_list):
        if len(worker_list) > self.pool_size:
            self.pool_size = len(worker_list) + 1
        super().call_workers(worker_list)
