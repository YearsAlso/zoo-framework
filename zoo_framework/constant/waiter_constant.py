class WaiterConstant:
    """调度器常量。

    已实现的调度模式：``WORKER_MODE_THREAD`` 与 ``WORKER_MODE_THREAD_POOL``。
    未实现的调度模式（占位）：``WORKER_MODE_PROCESS`` 与 ``WORKER_MODE_PROCESS_POOL`` ——
    进程模式要求 Worker 可 pickle 并提供跨进程通信，尚未提供实现。
    请求未实现的模式 MUST 被明确拒绝，MUST NOT 静默按其他模式执行。
    """

    # 已实现的调度模式
    WORKER_MODE_THREAD = "thread"
    WORKER_MODE_THREAD_POOL = "thread_pool"

    # 未实现（占位）：仅供调用方表达意图，当前会被显式拒绝
    WORKER_MODE_PROCESS = "process"
    WORKER_MODE_PROCESS_POOL = "process_pool"

    # 已实现的调度模式集合，供校验使用
    IMPLEMENTED_WORKER_MODES = (WORKER_MODE_THREAD, WORKER_MODE_THREAD_POOL)

    # Worker 结果上报主题。
    # 所有 Worker 的结果统一投递到本主题；接收方按 WorkerResult.worker_name 过滤，
    # 而不再由 Worker 各自的类名拼接出独立主题。
    WORKER_RESULT_TOPIC = "waiter"
