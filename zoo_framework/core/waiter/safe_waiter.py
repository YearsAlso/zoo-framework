from .base_waiter import BaseWaiter


class SafeWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
    
    def execute_service(self, workers):
        # 等待所有worker执行完成后再继续执行
        pass
    
    def dispatch_worker(self, worker):
        pass
    
    def worker_report(self, worker):
        pass
