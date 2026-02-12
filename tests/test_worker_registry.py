"""Worker Registry 测试

测试 WorkerRegistry 的注册、查找等功能
"""

import pytest
from zoo_framework.core.worker_registry import WorkerRegistry
from zoo_framework.workers import BaseWorker, WorkerProps


class TestWorker(BaseWorker):
    """测试用的 Worker 类"""
    
    def __init__(self, props: WorkerProps = None):
        super().__init__(props or {"name": "TestWorker"})


class TestWorkerRegistry:
    """WorkerRegistry 测试类"""

    def setup_method(self):
        """每个测试前创建新的注册表"""
        self.registry = WorkerRegistry()

    def test_get_nonexistent_worker_class(self):
        """测试获取不存在的 Worker 类"""
        result = self.registry.get_worker_class("nonexistent")
        assert result is None

    def test_has_worker(self):
        """测试检查 Worker 是否存在"""
        assert self.registry.has_worker("test_worker") is False

    def test_list_workers_empty(self):
        """测试列出空 Worker 列表"""
        workers = self.registry.list_workers()
        assert workers == []
