from threading import Thread

from zoo_framework.constant import WorkerConstant

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import ProcessPoolExecutor

from zoo_framework.workers import BaseWorker
from multiprocessing import Process


class BaseWaiter(object):
    _lock = None
    
    def __init__(self):
        from zoo_framework.params import WorkerParams
        # 获得模式
        self.worker_mode = WorkerParams.WORKER_RUN_MODE
        # 是否用池
        self.pool_enable = WorkerParams.WORKER_POOL_ENABLE
        # 获得资源池的大小
        self.pool_size = WorkerParams.WORKER_POOL_SIZE
        # 资源池初始化
        self.resource_pool = None
        self.workers = []
        self.worker_dict = {}
        
    def init_lock(self):
        pass
    
    # 集结worker们
    def call_workers(self, worker_list):
        self.workers = worker_list
        
        # 生成池或者列表
        if self.worker_mode == WorkerConstant.RUN_MODE_THREAD:
            if self.pool_enable:
                self.resource_pool = ProcessPoolExecutor(max_workers=self.pool_size)
        
        if self.worker_mode == WorkerConstant.RUN_MODE_PROCESS:
            if self.pool_enable:
                self.resource_pool = ThreadPoolExecutor(max_workers=self.pool_size)
    
    # 执行服务
    def execute_service(self):
        workers = []
        for worker in self.workers:
            if worker.is_loop:
                workers.append(worker)
            if self.worker_dict.get(worker.name) is None:
                self._dispatch_worker(worker)
        
        self.workers = workers
    
    def _dispatch_worker(self, worker):
        pass
    
    # 派遣worker
    @staticmethod
    def worker_running(master, worker):
        if not isinstance(worker, BaseWorker):
            return
        
        # master._dict_lock.acquire(blocking=True, timeout=1)
        master.worker_dict[worker.name] = worker
        # master._dict_lock.release()
        
        worker.run()
        
        # master._dict_lock.acquire(blocking=True, timeout=1)
        del master.worker_dict[worker.name]
        # master._dict_lock.release()
    
    # worker汇报结果
    @staticmethod
    def worker_report(self, worker):
        pass
