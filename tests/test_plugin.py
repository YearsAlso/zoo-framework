"""Plugin 系统测试

测试 Plugin 和 PluginManager
"""

import pytest
from unittest.mock import MagicMock

from zoo_framework.plugin import Plugin, PluginManager, WorkerDelayManager


class TestPlugin:
    """Plugin 测试类"""

    def test_plugin_creation(self):
        """测试创建 Plugin"""
        
        class TestPluginImpl(Plugin):
            @property
            def name(self):
                return "test_plugin"
            
            def initialize(self, context):
                pass
            
            def execute(self, *args, **kwargs):
                return "executed"
        
        plugin = TestPluginImpl()
        assert plugin.name == "test_plugin"
        assert plugin.execute() == "executed"

    def test_plugin_abstract_methods(self):
        """测试 Plugin 抽象方法"""
        
        class IncompletePlugin(Plugin):
            pass
        
        # 不能实例化缺少抽象方法实现的类
        with pytest.raises(TypeError):
            IncompletePlugin()

    def test_plugin_priority(self):
        """测试 Plugin 优先级"""
        
        class HighPriorityPlugin(Plugin):
            @property
            def name(self):
                return "high_priority"
            
            @property
            def priority(self):
                return 100
            
            def initialize(self, context):
                pass
            
            def execute(self, *args, **kwargs):
                pass
        
        plugin = HighPriorityPlugin()
        assert plugin.priority == 100


class TestPluginManager:
    """PluginManager 测试类"""

    def setup_method(self):
        """每个测试前清理"""
        PluginManager._plugins = []
        PluginManager._initialized = False

    def test_register_plugin(self):
        """测试注册插件"""
        
        class TestPluginImpl(Plugin):
            @property
            def name(self):
                return "test_plugin"
            
            def initialize(self, context):
                pass
            
            def execute(self, *args, **kwargs):
                return "test_result"
        
        plugin = TestPluginImpl()
        PluginManager.register(plugin)
        
        assert plugin in PluginManager._plugins

    def test_get_plugin(self):
        """测试获取插件"""
        
        class TestPluginImpl(Plugin):
            @property
            def name(self):
                return "test_plugin"
            
            def initialize(self, context):
                pass
            
            def execute(self, *args, **kwargs):
                pass
        
        plugin = TestPluginImpl()
        PluginManager.register(plugin)
        
        found = PluginManager.get_plugin("test_plugin")
        assert found == plugin

    def test_get_nonexistent_plugin(self):
        """测试获取不存在的插件"""
        
        result = PluginManager.get_plugin("nonexistent")
        assert result is None

    def test_execute_plugin(self):
        """测试执行插件"""
        
        class TestPluginImpl(Plugin):
            @property
            def name(self):
                return "test_plugin"
            
            def initialize(self, context):
                pass
            
            def execute(self, data):
                return f"processed: {data}"
        
        plugin = TestPluginImpl()
        PluginManager.register(plugin)
        
        result = PluginManager.execute("test_plugin", "input_data")
        assert result == "processed: input_data"

    def test_list_plugins(self):
        """测试列出所有插件"""
        
        class Plugin1(Plugin):
            @property
            def name(self):
                return "plugin1"
            
            def initialize(self, context):
                pass
            
            def execute(self, *args, **kwargs):
                pass
        
        class Plugin2(Plugin):
            @property
            def name(self):
                return "plugin2"
            
            def initialize(self, context):
                pass
            
            def execute(self, *args, **kwargs):
                pass
        
        PluginManager.register(Plugin1())
        PluginManager.register(Plugin2())
        
        plugins = PluginManager.list_plugins()
        assert "plugin1" in plugins
        assert "plugin2" in plugins


class TestWorkerDelayManager:
    """WorkerDelayManager 测试类"""

    def setup_method(self):
        """每个测试前清理"""
        WorkerDelayManager._delays = {}

    def test_set_delay(self):
        """测试设置延迟"""
        WorkerDelayManager.set_delay("worker1", 5.0)
        
        assert "worker1" in WorkerDelayManager._delays
        assert WorkerDelayManager._delays["worker1"] == 5.0

    def test_get_delay(self):
        """测试获取延迟"""
        WorkerDelayManager.set_delay("worker1", 3.0)
        
        delay = WorkerDelayManager.get_delay("worker1")
        assert delay == 3.0

    def test_get_delay_default(self):
        """测试获取默认延迟"""
        delay = WorkerDelayManager.get_delay("unknown_worker")
        assert delay == 1.0  # 默认值

    def test_clear_delay(self):
        """测试清除延迟"""
        WorkerDelayManager.set_delay("worker1", 5.0)
        WorkerDelayManager.clear_delay("worker1")
        
        assert "worker1" not in WorkerDelayManager._delays

    def test_clear_all_delays(self):
        """测试清除所有延迟"""
        WorkerDelayManager.set_delay("worker1", 1.0)
        WorkerDelayManager.set_delay("worker2", 2.0)
        
        WorkerDelayManager.clear_all()
        
        assert len(WorkerDelayManager._delays) == 0
