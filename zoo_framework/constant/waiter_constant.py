class WaiterConstant:
    """Scheduler constants.

    Implemented worker modes: ``WORKER_MODE_THREAD``,
    ``WORKER_MODE_THREAD_POOL`` and ``WORKER_MODE_EVENT_LOOP``.
    Unimplemented modes (placeholders): ``WORKER_MODE_PROCESS`` and
    ``WORKER_MODE_PROCESS_POOL`` - process modes require pickleable Workers
    and cross-process communication, no implementation provided yet.
    A request for an unimplemented mode MUST be rejected explicitly and
    MUST NOT silently run as another mode.
    """

    # Implemented worker modes
    WORKER_MODE_THREAD = "thread"
    WORKER_MODE_THREAD_POOL = "thread_pool"
    # 常驻事件循环执行模型（issue #235）：在独立守护线程上常驻一个事件循环，
    # 只接纳协程能力 Worker（AsyncWorker 子类），其余显式拒绝。
    WORKER_MODE_EVENT_LOOP = "event_loop"

    # Unimplemented (placeholders): let callers state intent; explicitly
    # rejected at present
    WORKER_MODE_PROCESS = "process"
    WORKER_MODE_PROCESS_POOL = "process_pool"

    # The implemented modes set, for validation
    IMPLEMENTED_WORKER_MODES = (
        WORKER_MODE_THREAD,
        WORKER_MODE_THREAD_POOL,
        WORKER_MODE_EVENT_LOOP,
    )

    # The Worker result topic.
    # All Workers' results are delivered to this unified topic; receivers
    # filter by WorkerResult.worker_name, instead of each Worker deriving
    # its own topic from its class name.
    WORKER_RESULT_TOPIC = "waiter"
