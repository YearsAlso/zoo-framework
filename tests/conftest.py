"""Pytest 配置和共享 fixtures

此模块包含 pytest 的共享配置和 fixtures
"""

import pytest


def _reset_registries() -> None:
    """复位框架的进程级实例与注册表——清单由登记表生成，不再手抄.

    变更 declare-debt-carriers（issue #50 切片一）：原先此处逐条硬编码复位
    （容器 / 两个类属性 / WorkerRegistry / 通道配置，再加 #51 补的封位与世代），
    新增进程级共享只能靠人记得加行。现在唯一真源是
    `zoo_framework.core.process_state.CARRIERS`——每项带归类声明与复位动作；
    tests/test_process_state_registry.py 扫描未登记的新载体并判失败。
    """
    from zoo_framework.core.process_state import reset_process_state

    reset_process_state()


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
