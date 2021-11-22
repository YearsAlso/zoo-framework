import threading
from concurrent.futures import ThreadPoolExecutor
from time import sleep

from core.waiter import WaiterFactory
from zoo_framework.utils import LogUtils

from .aop import worker_list, config_funcs
from .params_factory import ParamsFactory


class Master(object):
    _dict_lock = threading.Lock()
    worker_dict = {}
    
    def __init__(self, loop_interval=1):
        # load params
        ParamsFactory("./config.json")
        self.config()
        
        from zoo_framework.params import WorkerParams
        self.workers = worker_list
        self.loop_interval = loop_interval
        
        # 根据策略生成waiter
        waiter = WaiterFactory.get_waiter(WorkerParams.WORKER_RUN_POLICY)
        if waiter is not None:
            self.waiter = waiter
            self.waiter.call_workers(self.workers)
        else:
            raise Exception("Master hasn't available waiter,the application can't start.")
    
    def config(self):
        for key, value in config_funcs.items():
            value()
    
    def run(self):
        while True:
            self.waiter.execute_service()
            if self.loop_interval > 0:
                LogUtils.info("Master Sleep")
                sleep(self.loop_interval)
