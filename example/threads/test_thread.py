from time import sleep

from zoo_framework import LogUtils, worker, StateMachineManager

from zoo_framework.workers import BaseWorker


@worker(count=6)
class TestThread(BaseWorker):
    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": False,
            "delay_time": 1,
            "name": "TestThread"
        })
        self.is_loop = True

    def _execute(self):
        LogUtils.debug("Test", TestThread.__name__)

        StateMachineManager().set_state("Test", "Test", "Test")
        # sleep(20)
