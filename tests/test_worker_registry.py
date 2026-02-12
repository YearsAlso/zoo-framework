"""Worker Registry 测试

测试 WorkerRegistry 的注册、查找等功能
"""

import pytest
from zoo_framework.core.worker_registry import WorkerRegistry
from zoo_framework.workers import BaseWorker, WorkerProps


class TestWorker:
    """测试用的 Worker 类"""
    pass


class TestWorkerRegistry:
    """WorkerRegistry 测试类"""

    def setup_method(self):
        """每个测试前创建新的注册表"""
        self.registry = WorkerRegistry()

    def test_register_worker_class(self):
        """测试注册 Worker 类"""
        self.registry.register("test_worker", TestWorker)
        
        assert "test_worker" in self.registry._worker_classes
        assert self.registry._worker_classes["test_worker"] == TestWorker

    def test_register_worker_instance(self):
        """测试注册 Worker 实例"""
        worker = TestWorker()
        self.registry.register_instance("test_instance", worker)
        
        assert "test_instance" in self.registry._worker_instances
        assert self.registry._worker_instances["test_instance"] == worker

    def test_get_worker_class(self):
        """测试获取 Worker 类"""
        self.registry.register("test_worker", TestWorker)
        cls = self.registry.get_worker_class("test_worker")
        
        assert cls == TestWorker

    def test_get_nonexistent_worker_class(self):
        """测试获取不存在的 Worker 类"""
        result = self.registry.get_worker_class("nonexistent")
        assert result is None

    def test_create_worker(self):
        """测试创建 Worker 实例"""
        self.registry.register("test_worker", TestWorker)
        instance = self.registry.create_worker("test_worker")
        
        assert isinstance(instance, TestWorker)

    def test_get_or_create_worker(self):
        """测试获取或创建 Worker"""
        self.registry.register("test_worker", TestWorker)
        
        # 第一次创建
        instance1 = self.registry.get_or_create_worker("test_worker")
        # 第二次获取同一实例
        instance2 = self.registry.get_or_create_worker("test_worker")
        
        assert instance1 is instance2

    def test_unregister(self):
        """测试注销 Worker"""
        self.registry.register("test_worker", TestWorker)
        assert "test_worker" in self.registry._worker_classes
        
        self.registry.unregister("test_worker")
        assert "test_worker" not in self.registry._worker_classes

    def test_list_workers(self):
        """测试列出所有 Worker"""
        class TestWorker1:
            pass
        
        class TestWorker2:
            pass
        
        self.registry.register("worker1", TestWorker1)
        self.registry.register("worker2", TestWorker2)
        
        workers = self.registry.list_workers()
        assert "worker1" in workers
        assert "worker2" in workers

    def test_clear(self):
        """测试清空注册表"""
        self.registry.register("test_worker", TestWorker)
        assert len(self.registry._worker_classes) > 0
        
        self.registry.clear()
        assert len(self.registry._worker_classes) == 0
        assert len(self.registry._worker_instances) == 0

    def test_register_decorator(self):
        """测试装饰器注册"""
        
        @self.registry.register_worker("decorated_worker")
        class DecoratedWorker:
            pass
        
        assert "decorated_worker" in self.registry._worker_classes
        assert self.registry._worker_classes["decorated_worker"] == DecoratedWorker

    def test_register_with_tags(self):
        """测试带标签注册"""
        self.registry.register("test_worker", TestWorker, tags=["tag1", "tag2"])
        
        metadata = self.registry.get_metadata("test_worker")
        assert "tag1" in metadata["tags"]
        assert "tag2" in metadata["tags"]

    def test_find_by_tag(self):
        """测试按标签查找"""
        class Worker1:
            pass
        
        class Worker2:
            pass
        
        self.registry.register("worker1", Worker1, tags=["group1"])
        self.registry.register("worker2", Worker2, tags=["group1"])
        
        results = self.registry.find_by_tag("group1")
        assert len(results) == 2

    def test_has_worker(self):
        """测试检查 Worker 是否存在"""
        assert self.registry.has_worker("test_worker") is False
        
        self.registry.register("test_worker", TestWorker)
        assert self.registry.has_worker("test_worker") is True
