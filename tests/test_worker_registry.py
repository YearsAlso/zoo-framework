"""Worker Registry 测试

测试 WorkerRegistry 的注册、查找等功能
"""

from zoo_framework.core.worker_registry import WorkerRegistry
from zoo_framework.workers import BaseWorker


def _new_worker_cls() -> type[BaseWorker]:
    """每次调用返回一个**新建**的 Worker 子类（同名重注册的输入）.

    新建而非复用同一个类，才能区分"注册表返回旧实例"与"注册表返回新类实例"——
    复用同一类时两次取用本就应是同一个对象，测不出缺陷。
    """

    class _SharedWorker(BaseWorker):
        def __init__(self):
            super().__init__({"name": "Shared", "is_loop": False, "delay_time": 0})

    return _SharedWorker


class TestWorkerRegistry:
    """WorkerRegistry 测试类"""

    def setup_method(self):
        """每个测试前创建新的注册表"""
        self.registry = WorkerRegistry()

    def test_get_nonexistent_worker(self):
        """测试获取不存在的 Worker"""
        result = self.registry.get_worker("nonexistent")
        assert result is None

    def test_get_metadata_nonexistent(self):
        """测试获取不存在的 Worker 元数据"""
        result = self.registry.get_metadata("nonexistent")
        assert result is None

    def test_get_workers_by_tag_empty(self):
        """测试按标签获取 Worker - 空结果"""
        result = self.registry.get_workers_by_tag("some_tag")
        assert result == []

    def test_get_workers_by_priority_empty(self):
        """测试按优先级获取 Worker - 空结果"""
        result = self.registry.get_workers_by_priority(100)
        assert result == []

    def test_get_all_workers_empty(self):
        """测试获取所有 Worker - 空结果"""
        result = self.registry.get_all_workers()
        assert result == {}

    def test_unregister_nonexistent(self):
        """测试注销不存在的 Worker"""
        # 应该不抛出异常
        self.registry.unregister("nonexistent")


class TestSameNameReregistration:
    """worker-lifecycle: 同名重注册 MUST NOT 被实例缓存吞掉（issue #227）.

    缺陷：用同名再次注册一个新类时，``get_worker`` 继续命中旧实例，新类永不被
    实例化且完全静默。修法为「重注册替换缓存实例」——新定义必须真正生效。
    """

    def setup_method(self):
        """每个测试前创建新的注册表"""
        self.registry = WorkerRegistry()

    def test_reregister_class_yields_new_class_instance(self):
        """Scenario: 同名重注册新类后取用的是新类实例."""
        first_cls = _new_worker_cls()
        second_cls = _new_worker_cls()

        self.registry.register_class("Shared", first_cls)
        first = self.registry.get_worker("Shared")
        assert type(first) is first_cls

        self.registry.register_class("Shared", second_cls)
        second = self.registry.get_worker("Shared")
        assert type(second) is second_cls, "同名重注册后仍返回旧类实例，新类从未被实例化"

    def test_reregister_factory_yields_new_factory_instance(self):
        """Scenario: 同名重注册新工厂后取用的是新工厂的产物."""
        self.registry.register_factory("Shared", _new_worker_cls())
        first = self.registry.get_worker("Shared")

        self.registry.register_factory("Shared", _new_worker_cls())
        second = self.registry.get_worker("Shared")

        assert type(second) is not type(first), "同名重注册工厂后仍返回旧工厂产物"

    def test_reregister_instance_replaces_cached_instance(self):
        """Scenario: 同名重注册实例后取用的是新实例."""
        cls = _new_worker_cls()
        self.registry.register_class("Shared", cls)
        self.registry.get_worker("Shared")  # 触发延迟实例化缓存

        replacement = cls()
        self.registry.register_instance("Shared", replacement)

        assert self.registry.get_worker("Shared") is replacement

    def test_reregister_same_class_keeps_cached_instance(self):
        """同名重注册**同一个类**是幂等的：仅更新元数据，缓存实例保留.

        这条保证 ``Master`` 可重复构造（每次都重新注册默认 Worker 类）而不
        凭空重建实例。
        """
        cls = _new_worker_cls()
        self.registry.register_class("Shared", cls)
        first = self.registry.get_worker("Shared")

        self.registry.register_class("Shared", cls, metadata={"priority": 7})

        assert self.registry.get_worker("Shared") is first, "同一类重注册不应丢弃缓存实例"
        assert self.registry.get_metadata("Shared") == {"priority": 7}
