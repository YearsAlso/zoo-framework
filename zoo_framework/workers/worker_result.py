from typing import Any

from zoo_framework.constant import WaiterConstant


class WorkerResult:
    """The Worker execution result.

    All results are delivered to ``WaiterConstant.WORKER_RESULT_TOPIC``;
    ``worker_name`` identifies the Worker that produced the result, letting
    receivers filter by Worker. ``cls_name`` keeps the Worker's class name,
    letting receivers tell apart different instances of the same class.

    ``run_id`` / ``session_id`` are **explicit** run-identity fields:
    receivers can filter results by run or by session from them, and MUST
    NOT rely on implicit context (results may be produced in a worker thread,
    and worker threads do not inherit the caller's context variables). The
    values are stamped by the dispatch side at settlement.

    Args:
        topic: the delivery topic; empty falls into the unified result topic
        content: the return value of the Worker's execution body
        cls_name: the class name of the Worker that produced the result
        worker_name: the instance name (with ordinal) of the Worker that
            produced the result
        run_id: the identity of the run that produced the result
        session_id: the identity of the session the result belongs to
    """

    def __init__(
        self,
        topic: str,
        content: Any,
        cls_name: str,
        worker_name: str | None = None,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.topic = topic or WaiterConstant.WORKER_RESULT_TOPIC
        self.content = content
        self.cls_name = cls_name
        self.worker_name = worker_name
        self.run_id = run_id
        self.session_id = session_id

    def __repr__(self) -> str:
        return (
            f"WorkerResult(topic={self.topic}, cls_name={self.cls_name}, "
            f"worker_name={self.worker_name}, run_id={self.run_id})"
        )
