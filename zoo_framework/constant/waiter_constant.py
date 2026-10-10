class WaiterConstant:
    """Scheduler constants.

    Implemented worker modes: ``WORKER_MODE_THREAD`` and
    ``WORKER_MODE_THREAD_POOL``.
    Unimplemented modes (placeholders): ``WORKER_MODE_PROCESS`` and
    ``WORKER_MODE_PROCESS_POOL`` - process modes require pickleable Workers
    and cross-process communication, no implementation provided yet.
    A request for an unimplemented mode MUST be rejected explicitly and
    MUST NOT silently run as another mode.
    """

    # Implemented worker modes
    WORKER_MODE_THREAD = "thread"
    WORKER_MODE_THREAD_POOL = "thread_pool"

    # Unimplemented (placeholders): let callers state intent; explicitly
    # rejected at present
    WORKER_MODE_PROCESS = "process"
    WORKER_MODE_PROCESS_POOL = "process_pool"

    # The implemented modes set, for validation
    IMPLEMENTED_WORKER_MODES = (WORKER_MODE_THREAD, WORKER_MODE_THREAD_POOL)

    # The Worker result topic.
    # All Workers' results are delivered to this unified topic; receivers
    # filter by WorkerResult.worker_name, instead of each Worker deriving
    # its own topic from its class name.
    WORKER_RESULT_TOPIC = "waiter"
