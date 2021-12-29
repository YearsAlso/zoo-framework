from time import sleep

from zoo_framework import LogUtils, worker

from zoo_framework.workers import BaseWorker


@worker(count=6)
class TestThread(BaseWorker):
    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": False,
            "delay_time": 1,
            "name": "TestThread",
            "run_timeout": 3
        })
        self.is_loop = True
    
    def _execute(self):
        LogUtils.debug("Test", TestThread.__name__)
        sleep(20)
