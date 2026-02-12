"""Worker Registry 测试

测试 WorkerRegistry 的注册、查找等功能
"""

import pytest
from zoo_framework.core.worker_registry import WorkerRegistry, WorkerInfo


class TestWorkerRegistry:
    """WorkerRegistry 测试类"""

    def setup_method(self):
        """每个测试前清理注册表"""
        # 清理注册表
        WorkerRegistry._workers = {}
        WorkerRegistry._worker_classes = {}

    def test_register_worker_class(self):
        """测试注册 Worker 类"""
        
        class TestWorker:
            pass
        
        WorkerRegistry.register(TestWorker, name="test_worker")
        
        assert "test_worker" in WorkerRegistry._worker_classes
        assert WorkerRegistry._worker_classes["test_worker"] == TestWorker

    def test_register_worker_instance(self):
        """测试注册 Worker 实例"""
        
        class TestWorker:
            def __init__(self):
                self.name = "test_instance"
        
        worker = TestWorker()
        WorkerRegistry.register(worker, name="test_instance")
        
        assert "test_instance" in WorkerRegistry._workers

    def test_get_worker_class(self):
        """测试获取 Worker 类"""
        
        class TestWorker:
            pass
        
        WorkerRegistry.register(TestWorker, name="test_worker")
        cls = WorkerRegistry.get_worker_class("test_worker")
        
        assert cls == TestWorker

    def test_get_worker_instance(self):
        """测试获取 Worker 实例"""
        
        class TestWorker:
            def __init__(self):
                self.name = "test_instance"
        
        worker = TestWorker()
        WorkerRegistry.register(worker, name="test_instance")
        instance = WorkerRegistry.get_worker("test_instance")
        
        assert instance == worker

    def test_list_workers(self):
        """测试列出所有 Worker"""
        
        class TestWorker1:
            pass
        
        class TestWorker2:
            pass
        
        WorkerRegistry.register(TestWorker1, name="worker1")
        WorkerRegistry.register(TestWorker2, name="worker2")
        
        workers = WorkerRegistry.list_workers()
        assert "worker1" in workers
        assert "worker2" in workers

    def test_unregister_worker(self):
        """测试注销 Worker"""
        
        class TestWorker:
            pass
        
        WorkerRegistry.register(TestWorker, name="test_worker")
        assert "test_worker" in WorkerRegistry._worker_classes
        
        WorkerRegistry.unregister("test_worker")
        assert "test_worker" not in WorkerRegistry._worker_classes


class TestWorkerInfo:
    """WorkerInfo 测试类"""

    def test_worker_info_creation(self):
        """测试创建 WorkerInfo"""
        info = WorkerInfo(name="test", worker_class=str, tags=["tag1"])
        
        assert info.name == "test"
        assert info.worker_class == str
        assert "tag1" in info.tags

    def test_worker_info_has_tag(self):
        """测试检查标签"""
        info = WorkerInfo(name="test", worker_class=str, tags=["tag1", "tag2"])
        
        assert info.has_tag("tag1") is True
        assert info.has_tag("tag3") is False

    def test_worker_info_matches_tags(self):
        """测试匹配多个标签"""
        info = WorkerInfo(name="test", worker_class=str, tags=["tag1", "tag2"])
        
        assert info.matches_tags(["tag1"]) is True
        assert info.matches_tags(["tag1", "tag2"]) is True
        assert info.matches_tags(["tag3"]) is False
