"""综合测试模块

测试 zoo_framework 的主要功能
"""

import pytest
import os
import tempfile

# Worker 测试
from zoo_framework.workers import BaseWorker, WorkerResult, WorkerProps

# FIFO 测试
from zoo_framework.fifo import EventFIFO
from zoo_framework.fifo.base_fifo import BaseFIFO
from zoo_framework.fifo.node.event_fifo_node import EventNode, PriorityLevel

# Utils 测试
from zoo_framework.utils import LogUtils, FileUtils
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

# Params 测试
from zoo_framework.params import EventParams, LogParams, WorkerParams

# Reactor 测试
from zoo_framework.reactor.event_reactor_req import (
    EventReactorReq,
    ChannelType,
    ChannelManager,
)

# StateMachine 测试
from zoo_framework.statemachine import StateMachineManager

# Plugin 测试
from zoo_framework.plugin import Plugin, PluginManager, WorkerDelayManager


# ==================== Worker Tests ====================

class TestBaseWorker:
    """BaseWorker 测试类"""

    def test_worker_init_with_props(self):
        """测试使用 props 初始化 Worker"""
        props = {
            "is_loop": True,
            "delay_time": 1.5,
            "name": "TestWorker"
        }
        worker = BaseWorker(props)
        assert worker._props == props
        assert worker.is_loop() is True
        assert "TestWorker" in worker.name

    def test_worker_init_defaults(self):
        """测试 Worker 默认属性"""
        props = {"name": "TestWorker"}
        worker = BaseWorker(props)
        assert worker.is_loop() is False
        assert "TestWorker" in worker.name

    def test_worker_execute(self):
        """测试 Worker _execute 方法可以调用"""
        worker = BaseWorker({"name": "TestWorker"})
        result = worker._execute()
        assert result is None

    def test_worker_run(self):
        """测试 Worker run 方法"""
        worker = BaseWorker({"name": "TestWorker"})
        result = worker.run()
        assert isinstance(result, WorkerResult)


class TestWorkerProps:
    """WorkerProps 测试类"""

    def test_worker_props_init(self):
        """测试 WorkerProps 初始化"""
        props = WorkerProps("TestWorker", True, 2.0)
        assert props.name == "TestWorker"
        assert props.is_loop is True
        assert props.delay_time == 2.0


class TestWorkerResult:
    """WorkerResult 测试类"""

    def test_worker_result_init(self):
        """测试 WorkerResult 初始化"""
        result = WorkerResult("test_topic", "test_content", "TestClass")
        assert result.topic == "test_topic"
        assert result.content == "test_content"
        assert result.cls_name == "TestClass"


# ==================== FIFO Tests ====================

class TestEventNode:
    """EventNode 测试类"""

    def test_event_node_init(self):
        """测试 EventNode 初始化"""
        node = EventNode("test.topic", "test_content")
        assert node.topic == "test.topic"
        assert node.content == "test_content"
        assert node.priority == 0

    def test_event_node_with_priority(self):
        """测试带优先级的 EventNode"""
        node = EventNode("test.topic", "content", priority=100)
        assert node.priority == 100

    def test_event_node_priority_level(self):
        """测试 PriorityLevel"""
        node = EventNode("test.topic", "content", priority_level=PriorityLevel.HIGH)
        assert node.priority == PriorityLevel.HIGH.value

    def test_event_node_effective_priority(self):
        """测试有效优先级计算"""
        node = EventNode("test.topic", "content", priority=100)
        assert node.get_effective_priority() >= 100


class TestEventFIFO:
    """EventFIFO 测试类"""

    def test_fifo_init(self):
        """测试 EventFIFO 初始化"""
        fifo = EventFIFO()
        assert fifo is not None

    def test_fifo_push_and_pop(self):
        """测试 FIFO 入队和出队"""
        # 注意：BaseFIFO 使用类变量，需要清理
        BaseFIFO._fifo = []
        fifo = EventFIFO()
        fifo.push_value("test_value")
        assert BaseFIFO.size() > 0
        popped = BaseFIFO.pop_value()
        assert popped is not None

    def test_fifo_dispatch(self):
        """测试 FIFO dispatch"""
        BaseFIFO._fifo = []
        fifo = EventFIFO()
        fifo.dispatch("test.topic", "test_content", "test_provider")
        assert BaseFIFO.size() > 0


# ==================== Utils Tests ====================

class TestLogUtils:
    """LogUtils 测试类"""

    def test_log_utils_methods(self):
        """测试 LogUtils 方法可以正常调用"""
        LogUtils.info("Test info message")
        LogUtils.error("Test error message")
        LogUtils.debug("Test debug message")


class TestFileUtils:
    """FileUtils 测试类"""

    def test_file_exists(self):
        """测试文件存在检查"""
        assert FileUtils.file_exists("pyproject.toml") is True
        assert FileUtils.file_exists("nonexistent_file_xyz.txt") is False

    def test_dir_exists(self):
        """测试目录存在检查"""
        assert FileUtils.dir_exists("zoo_framework") is True
        assert FileUtils.dir_exists("nonexistent_dir_xyz") is False

    def test_get_file_parent(self):
        """测试获取文件父目录"""
        parent = FileUtils.get_file_parent("zoo_framework/core/master.py")
        assert parent == "zoo_framework/core"

    def test_get_file_name(self):
        """测试获取文件名"""
        name = FileUtils.get_file_name("zoo_framework/core/master.py")
        assert name == "master.py"

    def test_create_and_remove_file(self):
        """测试创建和删除文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            FileUtils.create_file(test_file)
            assert os.path.exists(test_file)
            FileUtils.file_remove(test_file)
            assert not os.path.exists(test_file)

    def test_get_file_size(self):
        """测试获取文件大小"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_path = f.name
            f.write("12345")
        try:
            size = FileUtils.get_file_size(temp_path)
            assert size == 5
        finally:
            os.unlink(temp_path)


class TestThreadSafeDict:
    """ThreadSafeDict 测试类"""

    def test_thread_safe_dict_init(self):
        """测试 ThreadSafeDict 初始化"""
        d = ThreadSafeDict()
        assert d is not None

    def test_thread_safe_dict_set_get(self):
        """测试 ThreadSafeDict 设置和获取"""
        d = ThreadSafeDict()
        d["key"] = "value"
        assert d["key"] == "value"
        assert d.get("key") == "value"

    def test_thread_safe_dict_keys(self):
        """测试 ThreadSafeDict 获取所有键"""
        d = ThreadSafeDict()
        d["key1"] = "value1"
        d["key2"] = "value2"
        keys = d.get_keys()
        assert "key1" in keys
        assert "key2" in keys

    def test_thread_safe_dict_contains(self):
        """测试 ThreadSafeDict contains"""
        d = ThreadSafeDict()
        d["key"] = "value"
        assert "key" in d
        assert "nonexistent" not in d


# ==================== Params Tests ====================

class TestEventParams:
    """EventParams 测试类"""

    def test_event_params_exist(self):
        """测试 EventParams 存在"""
        assert hasattr(EventParams, 'EVENT_JOIN_TIMEOUT')


class TestLogParams:
    """LogParams 测试类"""

    def test_log_params_exist(self):
        """测试 LogParams 存在"""
        assert hasattr(LogParams, 'LOG_LEVEL')


class TestWorkerParams:
    """WorkerParams 测试类"""

    def test_worker_params_exist(self):
        """测试 WorkerParams 存在"""
        assert hasattr(WorkerParams, 'WORKER_RUN_POLICY')


# ==================== Reactor Tests ====================

class TestChannelType:
    """ChannelType 测试类"""

    def test_channel_type_values(self):
        """测试 ChannelType 枚举值"""
        assert ChannelType.DEFAULT.value == "default"
        assert ChannelType.SYSTEM.value == "system"
        assert ChannelType.BUSINESS.value == "business"


class TestEventReactorReq:
    """EventReactorReq 测试类"""

    def test_event_reactor_req_init(self):
        """测试 EventReactorReq 初始化"""
        req = EventReactorReq(
            topic="test.topic",
            content="test_content",
            reactor_name="test_reactor"
        )
        assert req.topic == "test.topic"
        assert req.content == "test_content"
        assert req.channel == ChannelType.DEFAULT.value

    def test_event_reactor_req_with_channel(self):
        """测试带通道的 EventReactorReq"""
        req = EventReactorReq(
            topic="test.topic",
            content="test_content",
            reactor_name="test_reactor",
            channel=ChannelType.BUSINESS.value,
            priority=10
        )
        assert req.channel == ChannelType.BUSINESS.value
        assert req.priority == 10

    def test_event_reactor_req_match_channel(self):
        """测试通道匹配"""
        req = EventReactorReq(
            topic="test.topic",
            content="test_content",
            reactor_name="test_reactor",
            channel=ChannelType.BUSINESS.value
        )
        assert req.match_channel([ChannelType.BUSINESS.value]) is True
        assert req.match_channel([ChannelType.SYSTEM.value]) is False


class TestChannelManager:
    """ChannelManager 测试类"""

    def test_channel_manager_init(self):
        """测试 ChannelManager 初始化"""
        manager = ChannelManager()
        assert manager is not None

    def test_channel_manager_register_channel(self):
        """测试注册通道"""
        manager = ChannelManager()
        manager.register_channel("custom_channel", ["topic1", "topic2"])
        assert manager.is_channel_valid("custom_channel") is True
        assert manager.is_channel_valid("invalid_channel") is False


# ==================== StateMachine Tests ====================

class TestStateMachineManager:
    """StateMachineManager 测试类"""

    def test_state_machine_manager_singleton(self):
        """测试 StateMachineManager 单例"""
        sm1 = StateMachineManager()
        sm2 = StateMachineManager()
        assert sm1 is sm2

    def test_set_and_get_state(self):
        """测试设置和获取状态"""
        sm = StateMachineManager()
        sm.set_state("test_machine", "test.key", "test_value")
        value = sm.get_state("test_machine", "test.key")
        assert value == "test_value"


# ==================== Plugin Tests ====================

class MockPlugin(Plugin):
    """测试用插件"""
    name = "mock_plugin"
    version = "1.0.0"

    def initialize(self, context=None):
        pass

    def destroy(self):
        pass


class TestPlugin:
    """Plugin 测试类"""

    def test_plugin_init(self):
        """测试 Plugin 初始化"""
        plugin = MockPlugin()
        assert plugin.name == "mock_plugin"
        assert plugin.version == "1.0.0"


class TestWorkerDelayManager:
    """WorkerDelayManager 测试类"""

    def test_worker_delay_manager_init(self):
        """测试 WorkerDelayManager 初始化"""
        manager = WorkerDelayManager()
        assert manager is not None

    def test_worker_delay_manager_set_get_delay(self):
        """测试设置和获取延迟"""
        manager = WorkerDelayManager()
        manager.set_delay("test_worker", 3.0)
        delay = manager.get_delay("test_worker")
        assert delay == 3.0
