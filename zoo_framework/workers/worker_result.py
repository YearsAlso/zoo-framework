from zoo_framework.constant import WaiterConstant


class WorkerResult:
    """Worker 执行结果。

    所有结果统一投递到 ``WaiterConstant.WORKER_RESULT_TOPIC``；``worker_name``
    标识产生该结果的 Worker，供接收方按 Worker 筛选。``cls_name`` 保留 Worker 的
    类名，便于接收方区分同类 Worker 的不同实例。

    ``run_id`` / ``session_id`` 是**显式**的运行标识字段：接收方据此可按运行或按
    会话筛选结果，MUST NOT 依赖隐式上下文（结果可能在工作线程里产生，而工作线程
    不会继承调用方的上下文变量）。字段值由派发侧在结算时盖章。

    Args:
        topic: 投递主题；为空时归入统一结果主题
        content: Worker 执行体的返回值
        cls_name: 产生结果的 Worker 类名
        worker_name: 产生结果的 Worker 实例名（含编号）
        run_id: 产生该结果的那次运行的标识
        session_id: 该结果所属会话的标识
    """

    def __init__(self, topic, content, cls_name, worker_name=None, run_id=None, session_id=None):
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
