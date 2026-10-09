from zoo_framework.core.container import ThreadSafety, process_scoped

from .event_reactor import EventReactor


# Declared SINGLE_THREAD rather than INSTANCE_GUARANTEED: the base class
# EventReactor's retry_strategy / retry_times are mutable fields read during
# execution, while worker_names / on_result are assigned by the caller outside
# dispatch, with no barrier between the two (recorded as F4 in the census).
# Nothing breaks today only because the assignments all happen in the
# single-threaded startup/binding phase - that is timing luck, not a guarantee.
@process_scoped(thread_safety=ThreadSafety.SINGLE_THREAD)
class WaiterResultReactor(EventReactor):
    """The Waiter result reactor.

    Subscribes to the unified result topic
    (``WaiterConstant.WORKER_RESULT_TOPIC``). The reactor itself does no
    business processing; it has two duties:

    - make that topic a first-class citizen on the event pipeline -
      ``bind_topic_reactor`` needs a registered target
    - provide a filter-by-worker-name entry point: set ``worker_names`` to
      receive results from only the named Workers

    ``worker_names`` being None means receive from all Workers. Received
    results are handed over via the optional ``on_result`` callback; the
    reactor itself never accumulates results, avoiding unbounded growth
    over long runs.
    """

    def __init__(self):
        super().__init__("WaiterResultReactor")
        self._event_timeout = 0
        # Receive results from only these Workers; None means no filtering
        self.worker_names: list[str] | None = None
        # The optional receive callback, signature (WorkerResult) -> None
        self.on_result = None
        self.set_event_callback(self._on_result)

    def accepts(self, result) -> bool:
        """Decide whether this result should be accepted by the reactor.

        Args:
            result: the Worker execution result

        Returns:
            whether to accept
        """
        if self.worker_names is None:
            return True
        return getattr(result, "worker_name", None) in self.worker_names

    def _on_result(self, req):
        result = req.content
        if not self.accepts(result):
            return
        if self.on_result is not None:
            self.on_result(result)
