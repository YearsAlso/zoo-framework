from .base_waiter import BaseWaiter


class SimpleWaiter(BaseWaiter):
    def run_service(self, workers):
        # 不等待
        pass
    
    def service_worker(self, worker):
        pass
