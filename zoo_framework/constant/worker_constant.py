class WorkerConstant:
    """Worker 运行模式与运行策略常量。

    已实现：``RUN_MODE_THREAD`` 与三种运行策略。
    ``RUN_MODE_PROCESS`` / ``RUN_MODE_COROUTINE`` 及其缩写为**未实现占位** ——
    进程模式要求 Worker 可 pickle，协程模式尚无调度入口。
    未实现的常量 MUST NOT 被静默当作其他模式使用。
    """

    # 运行模式
    RUN_MODE_THREAD = "thread"
    RUN_MODE_PROCESS = "process"  # 未实现（占位）
    RUN_MODE_COROUTINE = "coroutine"  # 未实现（占位）

    # 运行模式（缩写）
    RUN_MODE_THREAD_ABBREVIATE = "T"
    RUN_MODE_PROCESS_ABBREVIATE = "P"  # 未实现（占位）
    RUN_MODE_COROUTINE_ABBREVIATE = "C"  # 未实现（占位）

    # 已实现的运行模式集合，供校验使用
    IMPLEMENTED_RUN_MODES = (RUN_MODE_THREAD,)

    # 运行策略（三种均已实现，由 WaiterFactory 提供对应调度器）
    RUN_POLICY_SAFE = "safe"
    RUN_POLICY_SIMPLE = "simple"
    RUN_POLICY_STABLE = "stable"

    # 已实现的运行策略集合，供校验使用
    IMPLEMENTED_RUN_POLICIES = (RUN_POLICY_SIMPLE, RUN_POLICY_STABLE, RUN_POLICY_SAFE)
