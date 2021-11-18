from zoo_framework import LogUtils, worker

from zoo_framework.workers import BaseWorker

@worker()
class TestThread(BaseWorker):
    def __init__(self, props: dict):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 1,
            "name": "TestThread"
        })
        self.is_loop = True
    
    def _execute(self):
        print("Test", TestThread.__name__)
