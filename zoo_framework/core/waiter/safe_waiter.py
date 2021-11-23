from multiprocessing import Process
from threading import Thread

from zoo_framework.handler.event_reactor import EventReactor

from zoo_framework.constant import WorkerConstant
from .base_waiter import BaseWaiter


class SafeWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
        self.worker_state = {}
        self._src_worker_list = []
        self.rebuild_worker = False
    
    def call_workers(self, worker_list):
        super().call_workers(worker_list)
        self._src_worker_list = worker_list
    
    def _dispatch_worker(self, worker):
        # 等待所有worker执行完成后再继续执行
        if self.pool_enable:
            t = self.resource_pool.submit(self.worker_running, self, worker)
            t.add_done_callback(self.worker_report)
        elif self.worker_mode == WorkerConstant.RUN_MODE_PROCESS:
            p = Process(target=self.worker_running, args=(self, worker))
            p.start()
        elif self.worker_mode == WorkerConstant.RUN_MODE_THREAD:
            t = Thread(target=self.worker_running, args=(self, worker))
            t.start()
    
    # 执行服务
    def execute_service(self):
        for worker in self.workers:
            if self.worker_dict.get(worker.name) is None:
                self._dispatch_worker(worker)
        
        self.workers = []
        self.rebuild_workers()
    
    def rebuild_workers(self):
        # 所有内容全部执行完成
        if self.rebuild_worker:
            self.workers = self._src_worker_list
    
    @staticmethod
    def worker_report(worker):
        result = worker.result()
        if result is None:
            raise Exception("Some worker run error")
        
        cls_name = result.cls_name
        
        EventReactor.dispatch(result.topic, result.content)
