"""Worker Registry 测试

测试 WorkerRegistry 的注册、查找等功能
"""

import pytest
from zoo_framework.core.worker_registry import WorkerRegistry
from zoo_framework.workers import BaseWorker, WorkerProps


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
