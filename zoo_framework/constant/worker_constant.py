"""
    """WorkerConstant - 类功能描述

    TODO: 添加类功能详细描述
    """
worker_constant - zoo_framework/constant/worker_constant.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

class WorkerConstant:
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
