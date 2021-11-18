import threading
from concurrent.futures import ThreadPoolExecutor
from time import sleep

from .aop import worker_list, config_funcs
from .params_factory import ParamsFactory


class Master(object):
    _dict_lock = threading.Lock()
    worker_dict = {}
    
    def __init__(self, loop_interval=1):
        from zoo_framework.params import WorkerParams
        self.worker_mode = WorkerParams.WORKER_RUN_MODE
        self.worker_size = WorkerParams.WORKER_POOL_SIZE
        thread_pool = ThreadPoolExecutor(max_workers=self.worker_size)
        self.workers = worker_list
        self.worker_pool = thread_pool
        self.loop_interval = loop_interval
        # load params
        ParamsFactory("./config.json")
        self.config()
    
    def config(self):
        for key, value in config_funcs.items():
            value()
    
    @staticmethod
    def worker_defend(master, worker):
        master._dict_lock.acquire(blocking=True, timeout=1)
        master.worker_dict[worker.name] = worker
        master._dict_lock.release()
        
        worker.run()
        
        master._dict_lock.acquire(blocking=True, timeout=1)
        master.worker_dict[worker.name] = None
        master._dict_lock.release()
    
    @staticmethod
    def worder_destory(future):
        result = future.result()
    
    def _run(self):
        workers = []
        for worker in self.workers:
            if worker.is_loop:
                workers.append(worker)
            if self.worker_dict.get(worker.name) is None:
                t = self.worker_pool.submit(self.worker_defend, self, worker)
                t.add_done_callback(self.worder_destory)
        
        self.workers = workers
    
    def run(self):
        while True:
            self._run()
            if self.loop_interval > 0:
                sleep(self.loop_interval)
