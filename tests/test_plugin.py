"""Plugin 系统测试

测试 Plugin 和 PluginManager
"""

import pytest
from unittest.mock import MagicMock

from zoo_framework.plugin import Plugin, PluginManager


class TestPlugin:
    """Plugin 测试类"""

    def test_plugin_abstract_methods(self):
        """测试 Plugin 抽象方法"""
        
        class IncompletePlugin(Plugin):
            pass
        
        # 不能实例化缺少抽象方法实现的类
        with pytest.raises(TypeError):
            IncompletePlugin()


class TestPluginManager:
    """PluginManager 测试类"""

    def setup_method(self):
        """每个测试前清理"""
        PluginManager._plugins = {}

    def test_get_nonexistent_plugin(self):
        """测试获取不存在的插件"""
        result = PluginManager.get_plugin(plugin_name="nonexistent")
        assert result is None

    def test_list_plugins_empty(self):
        """测试列出空插件列表"""
        plugins = PluginManager.list_plugins()
        assert plugins == []
