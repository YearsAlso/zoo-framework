"""Plugin 系统测试

测试 Plugin 和 PluginManager
"""

import pytest
from zoo_framework.plugin import (
    Plugin, 
    PluginManager, 
    WorkerDelayManager,
    get_plugin_manager,
)


class TestWorkerDelayManager:
    """WorkerDelayManager 测试类"""

    def setup_method(self):
        """每个测试前创建新的管理器"""
        self.manager = WorkerDelayManager()

    def test_set_delay(self):
        """测试设置延迟"""
        self.manager.set_delay("worker1", 5.0)
        
        assert "worker1" in self.manager._delays
        assert self.manager._delays["worker1"] == 5.0

    def test_get_delay(self):
        """测试获取延迟"""
        self.manager.set_delay("worker1", 3.0)
        
        delay = self.manager.get_delay("worker1")
        assert delay == 3.0

    def test_get_delay_default(self):
        """测试获取默认延迟"""
        delay = self.manager.get_delay("unknown_worker")
        assert delay == 1.0  # 默认值

    def test_reset(self):
        """测试重置延迟"""
        self.manager.set_delay("worker1", 5.0)
        self.manager.reset("worker1")
        
        assert "worker1" not in self.manager._delays


class TestPluginManager:
    """PluginManager 测试类"""

    def setup_method(self):
        """每个测试前创建新的管理器"""
        self.manager = PluginManager()

    def test_get_nonexistent_plugin(self):
        """测试获取不存在的插件"""
        result = self.manager.get_plugin("nonexistent")
        assert result is None

    def test_get_registered_plugins_empty(self):
        """测试获取空注册列表"""
        plugins = self.manager.get_registered_plugins()
        assert plugins == []

    def test_get_loaded_plugins_empty(self):
        """测试获取空加载列表"""
        plugins = self.manager.get_loaded_plugins()
        assert plugins == []

    def test_context(self):
        """测试上下文操作"""
        self.manager.set_context("key1", "value1")
        
        assert self.manager.get_context("key1") == "value1"
        assert self.manager.get_context("key2", "default") == "default"
