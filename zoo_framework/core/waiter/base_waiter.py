from constant import WorkerConstant

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import ProcessPoolExecutor


class BaseWaiter(object):
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
        self.worker_list = []
    
    # 集结worker们
    def call_workers(self, worker_list):
        self.worker_list = worker_list
        
        # 生成池或者列表
        if self.worker_mode == WorkerConstant.RUN_MODE_THREAD:
            if self.pool_enable:
                self.resource_pool = ProcessPoolExecutor(max_workers=self.pool_size)
        
        if self.worker_mode == WorkerConstant.RUN_MODE_PROCESS:
            if self.pool_enable:
                self.resource_pool = ThreadPoolExecutor(max_workers=self.pool_size)
    
    # 执行服务
    def execute_service(self, workers):
        pass
    
    # 派遣worker
    def dispatch_worker(self, worker):
        pass
    
    # worker汇报结果
    def worker_report(self, worker):
        pass
