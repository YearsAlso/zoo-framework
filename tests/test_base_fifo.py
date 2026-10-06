import unittest

from zoo_framework.fifo import BaseFIFO


class BaseFIFOTester(unittest.TestCase):
    """BaseFIFO 用例.

    队列存储已由类级改为实例级（此前所有实例共享同一个列表），因此用例改为对
    实例操作，不再需要在 setUp 里清理类变量。
    """

    def test_put(self):
        """
        测试入队
        """
        fifo = BaseFIFO()
        fifo.push_value(1)
        fifo.push_value(2)
        fifo.push_value(3)
        self.assertEqual(fifo.size(), 3)

    def test_get(self):
        class TestFIFO(BaseFIFO):
            pass

        fifo = TestFIFO()
        fifo.push_value(1)

        self.assertEqual(fifo.pop_value(), 1)

    def test_instances_do_not_share_storage(self):
        """两个实例的队列相互隔离"""
        first = BaseFIFO()
        second = BaseFIFO()
        first.push_value("only-in-first")
        self.assertEqual(first.size(), 1)
        self.assertEqual(second.size(), 0)

    def test_pop_value_on_empty_returns_none(self):
        """空队 pop_value MUST 返回 None 而非抛 IndexError（事件消费路径依赖此兜底）."""
        fifo = BaseFIFO()
        self.assertIsNone(fifo.pop_value())
        fifo.push_value("x")
        self.assertEqual(fifo.pop_value(), "x")
        self.assertIsNone(fifo.pop_value())
