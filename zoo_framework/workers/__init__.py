from .base_worker import BaseWorker
from .worker_result import WorkerResult
from .worker_props import WorkerProps
from .state_machine_work import StateMachineWorker
from .worker_register import WorkerRegister
from .event_worker import EventWorker

# P2: 异步 Worker 支持
try:
    from .async_worker import (
        AsyncWorker,
        AsyncEventWorker,
        AsyncStateMachineWorker,
        AsyncWorkerPool,
        AsyncWorkerType,
    )
    ASYNC_WORKER_AVAILABLE = True
except ImportError:
    ASYNC_WORKER_AVAILABLE = False

__all__ = [
    "BaseWorker",
    "WorkerResult",
    "WorkerProps",
    "StateMachineWorker",
    "WorkerRegister",
    "EventWorker",
]

# 如果异步 Worker 可用，添加到导出列表
if ASYNC_WORKER_AVAILABLE:
    __all__.extend([
        "AsyncWorker",
        "AsyncEventWorker",
        "AsyncStateMachineWorker",
        "AsyncWorkerPool",
        "AsyncWorkerType",
    ])
