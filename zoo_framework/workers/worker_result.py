from zoo_framework.constant import WaiterConstant


class WorkerResult:
    """Worker 执行结果。

    所有结果统一投递到 ``WaiterConstant.WORKER_RESULT_TOPIC``；``worker_name``
    标识产生该结果的 Worker，供接收方按 Worker 筛选。``cls_name`` 保留 Worker 的
    类名，便于接收方区分同类 Worker 的不同实例。

    Args:
        topic: 投递主题；为空时归入统一结果主题
        content: Worker 执行体的返回值
        cls_name: 产生结果的 Worker 类名
        worker_name: 产生结果的 Worker 实例名（含编号）
    """

    def __init__(self, topic, content, cls_name, worker_name=None):
        self.topic = topic or WaiterConstant.WORKER_RESULT_TOPIC
        self.content = content
        self.cls_name = cls_name
        self.worker_name = worker_name

    def __repr__(self) -> str:
        return (
            f"WorkerResult(topic={self.topic}, cls_name={self.cls_name}, "
            f"worker_name={self.worker_name})"
        )
