# -*- coding: utf-8 -*-
import asyncio

from zoo_framework.workers import EventWorker
from zoo_framework.workers import StateMachineWorker
from zoo_framework.utils import LogUtils

from .aop import worker_register, config_funcs
from .params_factory import ParamsFactory


class Master(object):
    def __init__(self, loop_interval=1):
        # TODO: 创建各类注册器
        # TODO: loop_interval 这个参数有些多余，可以考虑去掉
        from zoo_framework.core.waiter import WaiterFactory
        # load params
        ParamsFactory("./config.json")
        self.config()

        from zoo_framework.params import WorkerParams
        self.worker_register = worker_register
        self.worker_register.register(StateMachineWorker.__name__, StateMachineWorker())
        self.worker_register.register(EventWorker.__name__, EventWorker())

        # TODO: add svm to manager worker
        self.loop_interval = loop_interval

        # 根据策略生成waiter
        waiter = WaiterFactory.get_waiter(WorkerParams.WORKER_RUN_POLICY)
        if waiter is not None:
            self.waiter = waiter
            self.waiter.call_workers(self.worker_register.get_all_worker())
        else:
            raise Exception("Master hasn't available waiter,the application can't start.")

    def change_waiter(self, waiter):
        if self.waiter is not None:
            raise Exception("")
        self.waiter = waiter

    def config(self):
        for key, value in config_funcs.items():
            value()

    async def perform(self):
        """
        执行任务
        """
        # TODO： 可以考虑使用异步的方式来执行
        while True:
            self.waiter.execute_service()
            if self.loop_interval > 0:
                LogUtils.debug("Master Sleep")
                await asyncio.sleep(self.loop_interval)

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.perform())
        loop.run_forever()
