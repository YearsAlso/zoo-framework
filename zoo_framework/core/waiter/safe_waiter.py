from .base_waiter import BaseWaiter


class SafeWaiter(BaseWaiter):
    """安全调度器：Worker 数量 MUST NOT 超过配置的资源池尺寸。

    与 simple 策略的区别在于超出时**拒绝**而非自动扩容——配置表达的意图被显式遵守，
    而不是被静默改写。
    """

    def __init__(self):
        BaseWaiter.__init__(self)

    def call_workers(self, worker_list):
        if len(worker_list) > self.pool_size:
            raise ValueError(
                f"Worker 数量 {len(worker_list)} 超过资源池尺寸 {self.pool_size}；"
                "请增大 worker:pool:size，或改用 simple / stable 策略"
            )
        super().call_workers(worker_list)
