"""waiter_constant - zoo_framework/constant/waiter_constant.py

等待器常量模块，定义等待器相关的常量。

功能：
- 定义工作器运行模式常量
- 提供等待器配置选项
- 标准化常量命名

作者: XiangMeng
版本: 0.5.2-beta
"""


class WaiterConstant:
    """等待器常量类

    定义等待器和工作器相关的运行模式常量。
    """

    # 工作器运行模式
    WORKER_MODE_THREAD = "thread"
    WORKER_MODE_THREAD_POOL = "thread_pool"
    WORKER_MODE_PROCESS = "process"
    WORKER_MODE_PROCESS_POOL = "process_pool"

    # 等待器类型
    WAITER_TYPE_SIMPLE = "simple"
    WAITER_TYPE_STABLE = "stable"
    WAITER_TYPE_BASE = "base"

    # 超时设置
    DEFAULT_TIMEOUT = 30  # 默认超时时间（秒）
    MAX_TIMEOUT = 300     # 最大超时时间（秒）
    MIN_TIMEOUT = 1       # 最小超时时间（秒）

    # 重试设置
    DEFAULT_RETRY_COUNT = 3      # 默认重试次数
    DEFAULT_RETRY_DELAY = 1.0    # 默认重试延迟（秒）

    # 线程/进程池设置
    DEFAULT_POOL_SIZE = 4        # 默认池大小
    MAX_POOL_SIZE = 50           # 最大池大小
    MIN_POOL_SIZE = 1            # 最小池大小
