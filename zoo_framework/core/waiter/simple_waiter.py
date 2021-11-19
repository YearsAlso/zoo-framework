from .base_waiter import BaseWaiter


class SimpleWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
        
    def execute_service(self, workers):
        # 如果池化小于worker数量，则重新池化
        # 不等待
        pass
    
    def dispatch_worker(self, worker):
        pass

    def worker_report(self, worker):
        pass
