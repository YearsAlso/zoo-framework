"""Pytest 配置和共享 fixtures

此模块包含 pytest 的共享配置和 fixtures
"""

import pytest


def _reset_registries() -> None:
    """复位框架的进程级实例与注册表.

    框架里有三类跨用例存活的状态，不清掉会让"同名的 Worker / 主题 / 作用域"在不同用例
    之间互相串扰：

    - **容器的进程级实例**（事件反应器管理器、事件通道注册器、状态机管理器等）。
      它们原先由 ``@cage`` 提供、靠清空 ``cage_register_map`` 复位；``@cage`` 删除后
      改由 ``framework_container().reset()`` 复位——顺带也清掉了替换与单线程绑定。
    - **类级注册表**（``reactor_map`` / ``_channel_map``）：它们是类属性而非实例状态，
      容器复位带不走，需单独复位。
    - **容器之外的进程级状态**（``WorkerRegistry`` 的实例缓存、通道监听配置）：
      它们不走容器，仍各自复位。
    """
    from zoo_framework.core.aop.configure import unseal_config_funcs_for_tests
    from zoo_framework.core.container import framework_container
    from zoo_framework.core.params_factory import ParamsFactory
    from zoo_framework.core.worker_registry import get_worker_registry
    from zoo_framework.event.event_channel_register import EventChannelRegister
    from zoo_framework.reactor.event_reactor_manager import EventReactorManager
    from zoo_framework.reactor.event_reactor_req import get_channel_manager
    from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

    # 封位复位（#51 接缝）：避免上一个用例的 Master() 把 @configure 注册封到下个用例
    unseal_config_funcs_for_tests()

    # 配置世代与解析记录复位（#51 接缝）：stale 核对是"每进程一次性"的检查，
    # 用例之间必须从同一基准开始，否则前一个用例读到配置抬高的世代会让下一个
    # 用例里的导入时序被误判（真实跨用例的冻结在测试环境里不成立——每个用例
    # 都从头开始）。这两项同样是 #50 要收编的进程级状态。
    # 注：按属性取模块会被同名函数遮蔽（aop/__init__ 的 `from .params import params`），
    # 故直接导入字典对象本身——模块不会重绑它。
    from zoo_framework.core.aop.params import _resolved_generation

    ParamsFactory._generation = 0
    _resolved_generation.clear()

    # 容器的进程级实例 + 替换 + 单线程绑定
    framework_container().reset()

    # 类级注册表。这里可以直接用类本身——那 8 个管理器已是真类，
    # 不再需要 @cage 时代那种 `type(EventReactorManager())` 去"取回被替换掉的真类"。
    EventReactorManager.reactor_map = ThreadSafeDict()
    EventChannelRegister._channel_map = ThreadSafeDict()

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
    return {"is_loop": True, "delay_time": 1.0, "name": "TestWorker"}


@pytest.fixture
def sample_event_data():
    """提供示例事件数据"""
    return {"topic": "test.topic", "content": {"key": "value"}, "priority": 10}


@pytest.fixture
def sample_state_data():
    """提供示例状态数据"""
    return {"machine_name": "test_machine", "key": "test.key", "value": "test_value"}
