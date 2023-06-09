import unittest
from time import sleep

from zoo_framework.statemachine import StateMachineManager


class TestStateMache(unittest.TestCase):
    """
    状态机测试
    """

    def test_get_set(self):
        """
        测试获取和设置
        """

        set_value = 0
        StateMachineManager().set_state("Test", "Test.number", set_value)

        get_value = StateMachineManager().get_state("Test", "Test.number")
        self.assertEqual(set_value, get_value)

    def test_observe(self):
        """
        测试观察者
        """

        i = 0

        def _on_test_number_change(data):
            value = data.get('value')
            self.assertEqual(value, i)

        StateMachineManager().set_state("Test", "Test.number", 0)
        StateMachineManager().observe_state("Test", "Test.number", _on_test_number_change)

        # 循环设置
        for i in range(1, 10):
            StateMachineManager().set_state("Test", "Test.number", i)
            sleep(1)
