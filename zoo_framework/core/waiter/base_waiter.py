"""
base_waiter - 模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""


    _lock = None

    def __init__(self):
        from zoo_framework.params import WorkerParams

        # 获得模式
        self.worker_mode, self.pool_enable = self.get_worker_mode(WorkerParams.WORKER_POOL_ENABLE)
        # 获得资源池的大小
        self.pool_size = WorkerParams.WORKER_POOL_SIZE
        # 资源池初始化
        self.resource_pool = None

        # TODO:将 worker 使用register的方式注册，并且属性和方法都可以通过register的方式注册
        self.workers = []
        self.worker_props = {}
        self.register_handler()

    def get_worker_mode(self, pool_enable):
        """获得worker的模式."""
        if pool_enable:
            return WaiterConstant.WORKER_MODE_THREAD_POOL, pool_enable
        return WaiterConstant.WORKER_MODE_THREAD, pool_enable

    def register_handler(self):
        """注册handler."""
        # TODO: 不在使用主动注入，而是在创建注册器时，自动注册
        from zoo_framework.reactor.event_reactor_manager import EventReactorManager

        EventReactorManager().bind_topic_reactor("waiter", WaiterResultReactor())

    def init_lock(self):
        pass

    # 集结worker们
    def call_workers(self, worker_list: list):
        """集结worker们."""
        self.workers = worker_list

        # 生成池或者列表，这里使用线程池，如果使用进程池，需要考虑进程间通信，暂时不考虑
        if self.worker_mode == WaiterConstant.WORKER_MODE_THREAD_POOL:
            self.resource_pool = ThreadPoolExecutor(max_workers=self.pool_size)

    def __del__(self):
        if self.resource_pool is not None:
            self.resource_pool.shutdown(wait=True)

    # 执行服务
    def execute_service(self):
        """执行服务."""
        # 参与下次循环的worker
        next_loop_workers = []
        for worker in self.workers:
            self.worker_band(worker.name)

            if worker is None:
                continue

            if worker.is_loop:
                next_loop_workers.append(worker)

            # 判定是否超时
            self.worker_band(worker.name)

            if self.worker_props.get(worker.name) is None:
                self._dispatch_worker(worker)

        self.workers = next_loop_workers

    def _dispatch_worker(self, worker):
        """派遣 worker
        :param worker:
        :return:
        """
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
        """绑定worker
        :param worker_name: worker的名字.
        """
        # 根据模式
        worker_prop = self.worker_props.get(worker_name)
        if worker_prop is None:
            return

        worker_prop.get("worker")
        run_time = worker_prop.get("run_time")
        run_timeout = worker_prop.get("run_timeout")
        worker_prop.get("container")

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
        """Register the worker to self.worker_props
        :param worker: worker
        :param worker_container: worker running thread or process
        :return:
        """
        self.worker_props[worker.name] = {
            "worker": worker,
            "run_time": time.time(),
            "run_timeout": worker.run_timeout,
            "container": worker_container,
        }

    def unregister_worker(self, worker):
        if self.worker_props.get(worker.name) is not None:
            del self.worker_props[worker.name]

    def worker_running_callback(self, worker):
        self.unregister_worker(worker)

    # 派遣worker
    @staticmethod
    def worker_running(worker, callback=None):
        """派遣worker."""
        if not isinstance(worker, BaseWorker):
            return None

        result = worker.run()

        if callback is not None:
            callback(worker)

        return result

    # worker汇报结果
    @staticmethod
    def worker_report(worker):
        result = worker.result()
        EventReactorManager().dispatch(result.topic, result.content)
"""
