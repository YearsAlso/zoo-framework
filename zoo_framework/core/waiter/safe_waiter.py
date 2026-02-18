"""
safe_waiter - 模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""


safe_waiter - zoo_framework/core/waiter/safe_waiter.py

模块功能描述:


作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.reactor.event_reactor_manager import EventReactorManager

from .base_waiter import BaseWaiter


class SafeWaiter(BaseWaiter):
    """SafeWaiter - 类功能描述"""
    def __init__(self):
        BaseWaiter.__init__(self)
        self.worker_state = {}
        self._src_worker_list = []
        self.rebuild_worker = False
        self.futures = {}

    def call_workers(self, worker_list):
        if len(worker_list) > self.pool_size:
            raise Exception("Workers Number is too large")

        super().call_workers(worker_list)
        self._src_worker_list = worker_list

    # 执行服务
    def execute_service(self):
        for worker in self.workers:
            if self.worker_props.get(worker.name) is None:
                self._dispatch_worker(worker)

        self.workers = []
        self.rebuild_workers()

    def rebuild_workers(self):
        # 所有内容全部执行完成
        if self.rebuild_worker or self.pool_enable is False:
            self.workers = [worker for worker in self._src_worker_list if worker.is_loop]
        self.rebuild_worker = False

    # @staticmethod
    def worker_report(self, worker):
        result = worker.result()
        if result is None:
            raise Exception("Some worker run error")

        if len(self.worker_props.keys()) == 0:
            self.rebuild_worker = True

        EventReactorManager().dispatch(result.topic, result.content)
"""
