from .base_waiter import BaseWaiter


class SafeWaiter(BaseWaiter):
    def run_service(self, workers):
        pass
    
    def service_worker(self, worker):
        pass