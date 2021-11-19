from .base_waiter import BaseWaiter


class SimpleWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
        
    def run_service(self, workers):
        # 不等待
        pass
    
    def dispatch_worker(self, worker):
        pass

    def worker_report(self, worker):
        pass
