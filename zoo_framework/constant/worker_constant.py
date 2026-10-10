class WorkerConstant:
    """Worker run mode and run policy constants.

    Implemented: ``RUN_MODE_THREAD`` and three run policies.
    ``RUN_MODE_PROCESS`` / ``RUN_MODE_COROUTINE`` and their abbreviations
    are **unimplemented placeholders** - process mode requires pickleable
    Workers; coroutine mode has no scheduling entry yet.
    Unimplemented constants MUST NOT be silently treated as other modes.
    """

    # Run modes
    RUN_MODE_THREAD = "thread"
    RUN_MODE_PROCESS = "process"  # unimplemented (placeholder)
    RUN_MODE_COROUTINE = "coroutine"  # unimplemented (placeholder)

    # Run modes (abbreviations)
    RUN_MODE_THREAD_ABBREVIATE = "T"
    RUN_MODE_PROCESS_ABBREVIATE = "P"  # unimplemented (placeholder)
    RUN_MODE_COROUTINE_ABBREVIATE = "C"  # unimplemented (placeholder)

    # The implemented run modes set, for validation
    IMPLEMENTED_RUN_MODES = (RUN_MODE_THREAD,)

    # Policies when the pool size is insufficient (consumed by
    # ThreadPoolModel as a back-pressure policy):
    #   simple -> scale up; stable -> queue; safe -> reject
    # History: the three were once three scheduler classes
    # (SimpleWaiter / StableWaiter / SafeWaiter); their differences were
    # only in pool-size semantics, unrelated to concurrency primitives or
    # time semantics, so they were demoted to model parameters.
    RUN_POLICY_SAFE = "safe"
    RUN_POLICY_SIMPLE = "simple"
    RUN_POLICY_STABLE = "stable"

    # The implemented run policies set, for validation
    IMPLEMENTED_RUN_POLICIES = (RUN_POLICY_SIMPLE, RUN_POLICY_STABLE, RUN_POLICY_SAFE)
