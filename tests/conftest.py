"""Pytest 配置和共享 fixtures

此模块包含 pytest 的共享配置和 fixtures
"""

import pytest


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
