"""Pytest 配置和共享 fixtures

此模块包含 pytest 的共享配置和 fixtures
"""

import pytest


def _reset_registries() -> None:
    """复位框架的进程级单例与注册表.

    框架中有若干进程级单例（cage 单例表、事件响应器表、事件通道表、Worker 实例
    缓存、通道监听配置），它们跨越用例存活，会让"同名的 Worker / 主题"在不同用例
    之间互相串扰。
    """
    import sys

    from zoo_framework.core.worker_registry import get_worker_registry
    from zoo_framework.event.event_channel_register import EventChannelRegister
    from zoo_framework.reactor.event_reactor_manager import EventReactorManager
    from zoo_framework.reactor.event_reactor_req import get_channel_manager
    from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

    # 取回被 @cage 替换掉的两个真实类。这一步必须先做：取类需要实例，
    # 而复位 cage 表之后新建的实例会在构造时读到尚未清空的类级注册表。
    reactor_manager_cls = type(EventReactorManager())
    channel_register_cls = type(EventChannelRegister())

    # cage 单例（EventReactorManager / EventChannelRegister / StateMachineManager 等）。
    # 注意：必须经 sys.modules 取模块——`from .cage import cage` 使包属性
    # `zoo_framework.core.aop.cage` 指向**装饰器函数**，`import ... as` 拿到的也是函数，
    # 往函数上赋值不会影响 cage 闭包读取的模块全局变量。
    cage_module = sys.modules["zoo_framework.core.aop.cage"]
    cage_module.cage_register_map = ThreadSafeDict()

    # 类级注册表（与单例表无关，需单独复位）
    reactor_manager_cls.reactor_map = ThreadSafeDict()
    channel_register_cls._channel_map = ThreadSafeDict()

    # Worker 实例缓存
    registry = get_worker_registry()
    registry._worker_classes.clear()
    registry._worker_instances.clear()
    registry._worker_factories.clear()
    registry._worker_metadata.clear()

    # 通道监听配置
    channel_manager = get_channel_manager()
    channel_manager._channels.clear()
    channel_manager._reactor_channels.clear()


def _redirect_persistence_paths(tmp_path, monkeypatch) -> None:
    """把落盘路径重定向到临时目录.

    状态机 Worker 在停机时会保存状态，日志初始化会创建日志目录——两者都不应写进
    仓库根，否则每次跑测试都会产生未跟踪文件。
    """
    from zoo_framework.params import LogParams, StateMachineParams

    monkeypatch.setattr(StateMachineParams, "PICKLE_PATH", str(tmp_path / "zooStates.pic"))
    monkeypatch.setattr(LogParams, "LOG_BASE_PATH", str(tmp_path / "logs"))


@pytest.fixture(autouse=True)
def isolated_runtime_state(tmp_path, monkeypatch):
    """为每个用例隔离进程级全局状态与文件系统副作用."""
    _redirect_persistence_paths(tmp_path, monkeypatch)
    _reset_registries()
    yield
    _reset_registries()


@pytest.fixture
def sample_worker_props():
    """提供示例 Worker 属性"""
    return {
        "is_loop": True,
        "delay_time": 1.0,
        "name": "TestWorker"
    }


@pytest.fixture
def sample_event_data():
    """提供示例事件数据"""
    return {
        "topic": "test.topic",
        "content": {"key": "value"},
        "priority": 10
    }


@pytest.fixture
def sample_state_data():
    """提供示例状态数据"""
    return {
        "machine_name": "test_machine",
        "key": "test.key",
        "value": "test_value"
    }
