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

    def test_key_depth(self):
        """
        测试键深度
        """

        StateMachineManager().set_state("Test", "Test.number", 0)
        StateMachineManager().set_state("Test", "Test.number.1", 1)
        StateMachineManager().set_state("Test", "Test.number.1.1", 2)
        StateMachineManager().set_state("Test", "Test.number.1.1.1", 3)

        self.assertEqual(StateMachineManager().get_state("Test", "Test.number"), 0)
        self.assertEqual(StateMachineManager().get_state("Test", "Test.number.1"), 1)
        self.assertEqual(StateMachineManager().get_state("Test", "Test.number.1.1"), 2)
        self.assertEqual(StateMachineManager().get_state("Test", "Test.number.1.1.1"), 3)

    # 测试删除性能
    def test_delete(self):
        """
        测试删除性能
        """

        StateMachineManager().remove_state("Test", "Test.number")
        StateMachineManager().remove_state("Test", "Test.number.1")
        StateMachineManager().remove_state("Test", "Test.number.1.1")
        StateMachineManager().remove_state("Test", "Test.number.1.1.1")
