from .base_waiter import BaseWaiter


class StableWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
    
    def run_service(self, workers):
        # 是否使用池化
        pass
    
    def dispatch_worker(self, worker):
        pass
    
    def worker_report(self, worker):
        pass
