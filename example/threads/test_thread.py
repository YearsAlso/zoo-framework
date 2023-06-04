import random
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

    @staticmethod
    def _on_test_number_change(value):
        LogUtils.debug("Test", "Test number change to ")

    def _execute(self):
        LogUtils.debug("Test", TestThread.__name__)

        StateMachineManager().set_state("Test", "Test.number", random.Random().randint(0, 100))
        StateMachineManager().observe_state("Test", "Test.number", TestThread._on_test_number_change)
        sleep(1)
        LogUtils.info("Test", StateMachineManager().get_state("Test", "Test.number").get_value())
