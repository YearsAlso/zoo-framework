"""Core AOP 测试

测试 AOP 相关功能
"""

import pytest
from zoo_framework.core.aop import cage, event
from zoo_framework.core.aop.cage import Cage


class TestCage:
    """Cage 测试类"""

    def test_cage_decorator(self):
        """测试 cage 装饰器"""
        
        @cage
        class TestClass:
            def method1(self):
                return "method1"
            
            def method2(self):
                return "method2"
        
        # 测试类被装饰后能正常实例化
        instance = TestClass()
        assert instance is not None
        assert instance.method1() == "method1"
        assert instance.method2() == "method2"

    def test_cage_singleton_behavior(self):
        """测试 cage 的单例行为"""
        
        @cage
        class SingletonClass:
            def __init__(self):
                self.value = 0
            
            def increment(self):
                self.value += 1
                return self.value
        
        instance1 = SingletonClass()
        instance2 = SingletonClass()
        
        # 应该是同一个实例
        assert instance1 is instance2
        
        instance1.increment()
        assert instance2.value == 1


class TestEventDecorator:
    """Event 装饰器测试类"""

    def test_event_decorator_basic(self):
        """测试基本的 event 装饰器"""
        
        @event("test_topic", channel="test_channel")
        def handler(data):
            return f"handled: {data}"
        
        # 测试函数被装饰后能正常调用
        result = handler("test_data")
        assert result == "handled: test_data"

    def test_event_decorator_multiple(self):
        """测试多个 event 装饰器"""
        
        @event("topic1", channel="channel1")
        @event("topic2", channel="channel2")
        def multi_handler(data):
            return f"handled: {data}"
        
        result = multi_handler("test_data")
        assert result == "handled: test_data"

    def test_event_decorator_preserves_function_metadata(self):
        """测试 event 装饰器保留函数元数据"""
        
        @event("test_topic", channel="test_channel")
        def my_handler(data):
            """My handler docstring"""
            return f"handled: {data}"
        
        # 函数名应该被保留
        assert my_handler.__name__ == "my_handler"
