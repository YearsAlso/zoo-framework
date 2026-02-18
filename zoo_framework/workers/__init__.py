"""__init__ - zoo_framework/workers/__init__.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta

from .base_worker import BaseWorker
from .event_worker import EventWorker
from .state_machine_work import StateMachineWorker
from .worker_props import WorkerProps
from .worker_register import WorkerRegister
from .worker_result import WorkerResult

# P2: 异步 Worker 支持
try:
    from .async_worker import (
        AsyncEventWorker,  # noqa: F401
        AsyncStateMachineWorker,  # noqa: F401
        AsyncWorker,  # noqa: F401
        AsyncWorkerPool,  # noqa: F401
        AsyncWorkerType,  # noqa: F401
    )

    ASYNC_WORKER_AVAILABLE = True
except ImportError:
    ASYNC_WORKER_AVAILABLE = False

__all__ = [
    "BaseWorker",
    "EventWorker",
    "StateMachineWorker",
    "WorkerProps",
    "WorkerRegister",
    "WorkerResult",
]

# 如果异步 Worker 可用，添加到导出列表
if ASYNC_WORKER_AVAILABLE:
    __all__.extend(
        [
            "AsyncEventWorker",
            "AsyncStateMachineWorker",
            "AsyncWorker",
            "AsyncWorkerPool",
            "AsyncWorkerType",
        ]
    )
"""
