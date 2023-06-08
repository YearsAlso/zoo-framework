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
    def _on_test_number_change(data):
        value = data.get('value')
        version = data.get('version')
        LogUtils.info("Test", f"Test number change to {value}-{version}")

    def _on_create(self):
        StateMachineManager().set_state("Test", "Test.number", 0)
        StateMachineManager().observe_state("Test", "Test.number", self._on_test_number_change)

    def _execute(self):
        LogUtils.debug("Test", TestThread.__name__)

        state = StateMachineManager().get_state("Test", "Test.number")
        i = state.get_value()
        LogUtils.info("Test", i)
        i += 1
        StateMachineManager().set_state("Test", "Test.number", i)
        sleep(1)
