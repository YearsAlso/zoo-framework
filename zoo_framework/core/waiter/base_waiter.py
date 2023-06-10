import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from zoo_framework.register.worker_register import WorkerRegister
from zoo_framework.constant import WaiterConstant
from zoo_framework.handler.handler_register import HandlerRegister
from zoo_framework.handler.waiter_result_handler import WaiterResultHandler
from zoo_framework.workers import BaseWorker


class BaseWaiter(object):
    '''
    基础的waiter
    '''
    _lock = None

    def __init__(self):
        from zoo_framework.params import WorkerParams
        # 获得模式
        self.worker_mode, self.pool_enable = self.get_worker_mode(WorkerParams.WORKER_POOL_ENABLE)
        # 获得资源池的大小
        self.pool_size = WorkerParams.WORKER_POOL_SIZE
        # 资源池初始化
        self.resource_pool = None

        # TODO：将 worker 使用register的方式注册，并且属性和方法都可以通过register的方式注册
        self.workers = []
        self.worker_props = {}
        self.register_handler()

    def get_worker_mode(self, pool_enable):
        """
        获得worker的模式
        """
        if pool_enable:
            return WaiterConstant.WORKER_MODE_THREAD_POOL, pool_enable
        else:
            return WaiterConstant.WORKER_MODE_THREAD, pool_enable

    def register_handler(self):
        """
        注册handler
        """
        from zoo_framework.handler.handler_register import HandlerRegister
        HandlerRegister().register("waiter", WaiterResultHandler())

    def init_lock(self):
        pass

    # 集结worker们
    def call_workers(self, worker_register: WorkerRegister):
        self.workers = worker_register.get_all_worker()

        # 生成池或者列表
        if self.worker_mode == WaiterConstant.WORKER_MODE_THREAD_POOL:
            self.resource_pool = ThreadPoolExecutor(max_workers=self.pool_size)

    def __del__(self):
        if self.resource_pool is not None:
            self.resource_pool.shutdown(wait=True)

    # 执行服务
    def execute_service(self):
        workers = []
        for worker in self.workers:
            self.worker_band(worker.name)

            if worker is None:
                continue

            if worker.is_loop:
                workers.append(worker)

            # 判定是否超时
            self.worker_band(worker.name)

            if self.worker_props.get(worker.name) is None:
                self._dispatch_worker(worker)

        self.workers = workers

    def _dispatch_worker(self, worker):
        '''
        派遣 worker
        :param worker:
        :return:
        '''
        if self.worker_mode is WaiterConstant.WORKER_MODE_THREAD_POOL:
            t = self.resource_pool.submit(self.worker_running, worker, self.worker_running_callback)
            t.add_done_callback(self.worker_report)
            self.register_worker(worker, t)
        elif self.worker_mode is WaiterConstant.WORKER_MODE_THREAD:
            from threading import Thread
            t = Thread(target=self.worker_running, args=(worker, self.worker_running_callback))
            t.start()
            self.register_worker(worker, t)

    def worker_band(self, worker_name):
        '''
        绑定worker
        :param worker_name: worker的名字
        '''
        # 根据模式
        worker_prop = self.worker_props.get(worker_name)
        if worker_prop is None:
            return

        worker = worker_prop.get("worker")
        run_time = worker_prop.get("run_time")
        run_timeout = worker_prop.get("run_timeout")
        container = worker_prop.get("container")

        now_time = time.time()

        if run_timeout is None or run_timeout <= 0:
            return

        if (now_time - run_time) < run_timeout:
            return

        #
        # if self.worker_mode is WaiterConstant.WORKER_MODE_THREAD_POOL:
        #     if container.cancel() is False:
        #         return
        # elif self.worker_mode is WaiterConstant.WORKER_MODE_THREAD:
        #     container.kill()
        #
        # self.unregister_worker(worker)

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
        if self.worker_props.get(worker.name) is not None:
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
        HandlerRegister().dispatch(result.topic, result.content)
