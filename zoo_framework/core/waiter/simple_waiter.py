from zoo_framework.constant import WorkerConstant
from .base_waiter import BaseWaiter
from multiprocessing import Process
from threading import Thread


class SimpleWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
    
    def _dispatch_worker(self, worker):
        if self.pool_enable:
            t = self.resource_pool.submit(self.worker_running, self, worker)
            t.add_done_callback(self.worker_report)
        elif self.worker_mode == WorkerConstant.RUN_MODE_PROCESS:
            p = Process(target=self.worker_running, args=(self, worker))
            p.start()
        elif self.worker_mode == WorkerConstant.RUN_MODE_THREAD:
            t = Thread(target=self.worker_running, args=(self, worker))
            t.start()
