import re
from typing import Any

from zoo_framework.core.container import ThreadSafety, process_scoped

from .event_reactor import EventReactor

# 实例序号后缀：``BaseWorker.name`` 为注册名拼上 ``_<num>``（``ok`` → ``ok_1``）
_ORDINAL_SUFFIX_RE = re.compile(r"_\d+$")


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

    ``worker_names`` holds **registration names** (the suffix-free identity),
    so ``worker_names=['ok']`` receives the results of Worker ``ok`` whatever
    its instance ordinal is (``ok_1``, ``ok_2``, ...). Matching is exact, not
    prefix-based: ``ok`` MUST NOT match a Worker named ``ok2``. The
    ordinal-bearing instance name may also be listed explicitly, for callers
    that already know it. An empty/None ``worker_names`` means receive from
    all Workers.

    Received results are handed over via the optional ``on_result`` callback;
    the reactor itself never accumulates results, avoiding unbounded growth
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

    def accepts(self, result: Any) -> bool:
        """Decide whether this result should be accepted by the reactor.

        The filter is declared with the Worker's **registration name**
        (``worker_names=['ok']``), while the result carries the instance name
        including the ordinal (``ok_1``). Matching therefore compares the
        ordinal-free identity rather than the raw instance name; comparing the
        two directly never matched, which silently filtered **everything**
        out (issue #229).

        A result is accepted when any of its identities is in the filter:
        ``registry_name`` (the suffix-free field), the trailing-ordinal-stripped
        form of ``worker_name`` (covers results built outside
        ``BaseWorker.run``), or ``worker_name`` itself (the exact instance
        name, kept for backward compatibility). Matching stays exact - this is
        a real filter, not a prefix match.

        Args:
            result: the Worker execution result

        Returns:
            whether to accept
        """
        if self.worker_names is None:
            return True
        return bool(set(self.worker_names) & self._identity_candidates(result))

    @staticmethod
    def _identity_candidates(result: Any) -> set[str]:
        """Collect the identities a result can be matched by.

        Args:
            result: the Worker execution result

        Returns:
            The candidate identity strings; empty when the result carries none
        """
        candidates: set[str] = set()

        registry_name = getattr(result, "registry_name", None)
        if registry_name:
            candidates.add(str(registry_name))

        worker_name = getattr(result, "worker_name", None)
        if worker_name:
            worker_name = str(worker_name)
            candidates.add(worker_name)
            stripped = _ORDINAL_SUFFIX_RE.sub("", worker_name)
            if stripped:
                candidates.add(stripped)

        return candidates

    def _on_result(self, req):
        result = req.content
        if not self.accepts(result):
            return
        if self.on_result is not None:
            self.on_result(result)
