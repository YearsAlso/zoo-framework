from .base_waiter import BaseWaiter


class StableWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
    
    def execute_service(self, workers):
        # 不等待直接执行
        pass
    
    def dispatch_worker(self, worker):
        pass
    
    def worker_report(self, worker):
        pass
