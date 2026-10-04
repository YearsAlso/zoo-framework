"""Core AOP 测试

测试 AOP 相关功能
"""

from zoo_framework.core.aop import event
from zoo_framework.core.container import ThreadSafety, process_scoped


class TestProcessScoped:
    """``process_scoped`` 测试类.

    ``@cage`` 已随 scoped-container 删除。它原本承担的两件事——"装饰后类能正常实例化"
    与"进程内单例语义成立"——由 ``process_scoped`` 接手，故此处**断言语义保持不变**，
    只把主体换成新机制，并补上 ``@cage`` 做不到的那一条：类仍是真类。
    """

    def test_decorated_class_is_instantiable(self):
        """装饰后能正常实例化、方法可用（原 test_cage_decorator 的语义）."""

        @process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        class TestClass:
            def method1(self):
                return "method1"

            def method2(self):
                return "method2"

        instance = TestClass()
        assert instance is not None
        assert instance.method1() == "method1"
        assert instance.method2() == "method2"

    def test_process_singleton_behavior(self):
        """进程内单例语义成立、状态共享（原 test_cage_singleton_behavior 的语义）."""

        @process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
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

    def test_decorated_class_keeps_its_class_identity(self):
        """类型契约不被摧毁——这正是删除 ``@cage`` 的原因.

        ``@cage`` 把类换成工厂函数，于是 ``issubclass`` / ``isinstance`` 双双抛
        ``TypeError``（已实测并造成过一次 P0）。``process_scoped`` 不替换类。
        """

        @process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        class Typed:
            pass

        assert isinstance(Typed, type)
        assert issubclass(Typed, object) is True
        assert isinstance(Typed(), Typed) is True

    def test_init_runs_once_even_though_new_is_delegated(self):
        """``__new__`` 返回 ``cls`` 的实例，故 ``type.__call__`` 仍会再调一次 ``__init__``.

        若不做幂等保护，有实例状态的类第二次调用就会被重置——这正是实现必须挡住的地方。
        """
        inits = []

        @process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        class Stateful:
            def __init__(self):
                inits.append(1)
                self.state = {"n": 0}

        first = Stateful()
        first.state["n"] = 42

        assert Stateful().state["n"] == 42, "第二次构造把状态重置了"
        assert len(inits) == 1, f"__init__ 执行了 {len(inits)} 次"

    def test_subclass_does_not_inherit_process_identity(self):
        """给基类加一次装饰器不得把它的所有子类卷成同一个共享实例."""

        @process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        class Base:
            pass

        class Child(Base):
            pass

        assert Child() is not Child()
        assert type(Child()) is Child

    def test_reset_releases_the_process_instance(self):
        """进程级实例可被容器 ``reset()`` 复位——这是 ``@cage`` 从未有过的能力."""

        @process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        class Resettable:
            pass

        first = Resettable()
        from zoo_framework.core.container import framework_container

        released = framework_container().reset()

        assert first is not Resettable()
        assert any(name.endswith("Resettable") for name in released)


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

    def test_event_decorator_preserves_function_name(self):
        """测试 event 装饰器保留函数名"""

        @event("test_topic", channel="test_channel")
        def my_handler(data):
            """My handler docstring"""
            return f"handled: {data}"

        # 函数名应该被保留
        assert my_handler.__name__ == "my_handler"
