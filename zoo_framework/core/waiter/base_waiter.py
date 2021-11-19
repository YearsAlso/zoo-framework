from constant import WorkerConstant


class BaseWaiter(object):
    def __init__(self):
        from zoo_framework.params import WorkerParams
        # 获得模式
        self.worker_mode = WorkerParams.WORKER_RUN_MODE
        # 是否用池
        self.pool_enable = WorkerParams.WORKER_POOL_ENABLE
        # 获得资源池的大小
        self.worker_size = WorkerParams.WORKER_POOL_SIZE
    
    def call_workers(self, worker_list):
        self.worker_list = worker_list
        # 生成池或者列表
        if self.worker_mode == WorkerConstant.RUN_MODE_THREAD:
            if self.pool_enable:
                pass
            else:
                pass
        pass
    
    def run_service(self, workers):
        pass
    
    def dispatch_worker(self, worker):
        pass
    
    def worker_report(self, worker):
        pass
