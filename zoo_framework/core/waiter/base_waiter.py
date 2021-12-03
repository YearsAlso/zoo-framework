import time

from constant import WaiterConstant
from zoo_framework.handler.event_reactor import EventReactor

from zoo_framework.constant import WorkerConstant

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import ProcessPoolExecutor

from zoo_framework.handler.waiter_result_handler import WaiterResultHandler
from zoo_framework.workers import BaseWorker
from multiprocessing import Pool


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
        self.worker_props = {}
        self.register_handler()
    
    def get_worker_mode(self):
        if self.pool_enable:
            if self.worker_mode == WorkerConstant.RUN_MODE_PROCESS:
                return WaiterConstant.WORKER_MODE_PROCESS_POOL
            elif self.worker_mode == WorkerConstant.RUN_MODE_THREAD:
                return WaiterConstant.WORKER_MODE_THREAD_POOL
        elif self.worker_mode == WorkerConstant.RUN_MODE_PROCESS:
            return WaiterConstant.WORKER_MODE_PROCESS
        elif self.worker_mode == WorkerConstant.RUN_MODE_THREAD:
            return WaiterConstant.WORKER_MODE_THREAD
    
    def register_handler(self):
        from zoo_framework.handler.event_reactor import EventReactor
        EventReactor().register("waiter", WaiterResultHandler())
    
    def init_lock(self):
        pass
    
    # 集结worker们
    def call_workers(self, worker_list):
        self.workers = worker_list
        
        # 生成池或者列表
        if self.worker_mode == WorkerConstant.RUN_MODE_THREAD:
            if self.pool_enable:
                self.resource_pool = ThreadPoolExecutor(max_workers=self.pool_size)
        
        if self.worker_mode == WorkerConstant.RUN_MODE_PROCESS:
            if self.pool_enable:
                self.resource_pool = Pool(processes=self.pool_size)
    
    def __del__(self):
        if self.resource_pool is not None:
            self.resource_pool.shutdown(wait=True)
    
    # 执行服务
    def execute_service(self):
        workers = []
        for worker in self.workers:
            if worker is None:
                continue
            
            if worker.is_loop:
                workers.append(worker)
            if self.worker_props.get(worker.name) is None:
                self._dispatch_worker(worker)
        
        self.workers = workers
    
    def _dispatch_worker(self, worker):
        '''
        派遣 worker
        :param worker:
        :return:
        '''
        if self.worker_mode is WaiterConstant.WORKER_MODE_PROCESS_POOL:
            sub_res = self.resource_pool.apply_async(self.worker_running,
                                                     args=(worker, self.worker_running_callback))
            self.register_worker(worker, sub_res)
        elif self.worker_mode is WaiterConstant.WORKER_MODE_THREAD_POOL:
            t = self.resource_pool.submit(self.worker_running, worker, self.worker_running_callback)
            t.add_done_callback(self.worker_report)
            self.register_worker(worker, t)
        elif self.worker_mode is WaiterConstant.WORKER_MODE_PROCESS:
            from multiprocessing import Process
            p = Process(target=self.worker_running, args=(worker, self.worker_running_callback))
            p.start()
            self.register_worker(worker, p)
        elif self.worker_mode is WaiterConstant.WORKER_MODE_THREAD:
            from threading import Thread
            t = Thread(target=self.worker_running, args=(worker, self.worker_running_callback))
            t.start()
            self.register_worker(worker, t)
    
    def register_worker(self, worker, worker_container):
        '''
        register the worker to self.worker_props
        :param worker: worker
        :param worker_container: worker running thread or process
        :return:
        '''
        self.worker_props[worker.name] = {
            "worker": worker,
            "run_time": time.time(),
            "run_timeout": worker.run_timeout,
            "container": worker_container
        }
    
    def unregister_worker(self, worker):
        del self.worker_props[worker.name]
    
    def worker_running_callback(self, worker):
        self.unregister_worker(worker)
    
    # 派遣worker
    def worker_running(self, worker, callback=None):
        if not isinstance(worker, BaseWorker):
            return
        
        result = worker.run()
        
        if callback is not None:
            callback(worker)
        
        return result
    
    # worker汇报结果
    @staticmethod
    def worker_report(worker):
        result = worker.result()
        EventReactor().dispatch(result.topic, result.content)
