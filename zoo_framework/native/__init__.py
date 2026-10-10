"""zoo_framework.native — 原生任务执行（Python 编排 + 可选 Rust 扩展）.

公共面（变更 add-native-task-execution）：

- :class:`NativeTaskContract` / :class:`NativeContractDescriptor`: 契约数据类
- :class:`NativeTaskError` 三族: ``NativeInvalidInput`` / ``NativeTaskFailed`` / ``NativePanic``
- :class:`NativeAdapter`: 扩展加载 / 握手 / 转换 / 错误映射
- :class:`NativeTaskWorker`: 复用既有 Worker 生命周期的原生任务执行体
- :func:`get_native_adapter` / :func:`reset_native_adapter`: 进程级单例访问与复位
"""

from .adapter import NativeAdapter, get_native_adapter, reset_native_adapter
from .contract import (
    CONTRACT_VERSION,
    NativeContractDescriptor,
    NativeInvalidInput,
    NativePanic,
    NativeTaskContract,
    NativeTaskError,
    NativeTaskFailed,
)
from .worker import NativeTaskWorker

__all__ = [
    "CONTRACT_VERSION",
    "NativeAdapter",
    "NativeContractDescriptor",
    "NativeInvalidInput",
    "NativePanic",
    "NativeTaskContract",
    "NativeTaskError",
    "NativeTaskFailed",
    "NativeTaskWorker",
    "get_native_adapter",
    "reset_native_adapter",
]
