"""worker_constant - zoo_framework/constant/worker_constant.py

工作器常量模块，定义工作器相关的常量。

功能:
- 定义工作器运行模式和策略
- 提供标准化的常量命名
- 支持配置选项

作者: XiangMeng
版本: 0.5.2-beta
"""


class WorkerConstant:
    """工作器常量类

    定义工作器运行模式、策略和其他相关常量。
    """

    # worker 运行模式
    RUN_MODE_THREAD = "thread"
    RUN_MODE_PROCESS = "process"
    RUN_MODE_COROUTINE = "coroutine"

    # worker 运行模式（缩写）
    RUN_MODE_THREAD_ABBREVIATE = "T"
    RUN_MODE_PROCESS_ABBREVIATE = "P"
    RUN_MODE_COROUTINE_ABBREVIATE = "C"

    # 运行策略
    RUN_POLICY_SAFE = "safe"
    RUN_POLICY_SIMPLE = "simple"
    RUN_POLICY_STABLE = "stable"

    # 工作器状态
    WORKER_STATUS_IDLE = "idle"
    WORKER_STATUS_RUNNING = "running"
    WORKER_STATUS_COMPLETED = "completed"
    WORKER_STATUS_FAILED = "failed"
    WORKER_STATUS_CANCELLED = "cancelled"

    # 默认配置
    DEFAULT_WORKER_COUNT = 1
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_RETRY_COUNT = 3

    # 事件类型
    EVENT_TYPE_START = "start"
    EVENT_TYPE_COMPLETE = "complete"
    EVENT_TYPE_ERROR = "error"
    EVENT_TYPE_CANCEL = "cancel"

    # 日志级别
    LOG_LEVEL_DEBUG = "debug"
    LOG_LEVEL_INFO = "info"
    LOG_LEVEL_WARNING = "warning"
    LOG_LEVEL_ERROR = "error"
