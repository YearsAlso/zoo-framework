import unittest

from zoo_framework.fifo import BaseFIFO


class BaseFIFOTester(unittest.TestCase):

    def test_put(self):
        """
        测试入队
        """
        fifo = BaseFIFO()
        BaseFIFO.push_value(1)
        BaseFIFO.push_value(2)
        BaseFIFO.push_value(3)
        self.assertEqual(fifo.size(), 3)

    def test_get(self):
        class TestFIFO(BaseFIFO):
            _fifo = []

        TestFIFO.push_value(1)

        self.assertEqual(TestFIFO.pop_value(), 1)
