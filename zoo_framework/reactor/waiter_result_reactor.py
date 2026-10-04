from zoo_framework.core.container import ThreadSafety, process_scoped

from .event_reactor import EventReactor


# 声明为"仅限单线程"而不是"实例自身保证"：基类 EventReactor 的 retry_strategy /
# retry_times 是执行期读取的可变字段，而 worker_names / on_result 由调用方在派发之外
# 赋值，两者之间没有栅栏（清点时记为 F4）。当前不出事只是因为赋值都发生在启动/绑定期
# 的单线程阶段——那是时序上的侥幸，不是保证。
@process_scoped(thread_safety=ThreadSafety.SINGLE_THREAD)
class WaiterResultReactor(EventReactor):
    """Waiter 结果响应器.

    订阅统一的结果主题（``WaiterConstant.WORKER_RESULT_TOPIC``）。响应器自身不做业务
    处理，它的职责有两个：

    - 让该主题成为事件管道上的一等公民——``bind_topic_reactor`` 需要有注册对象
    - 提供按 Worker 名筛选的入口：设置 ``worker_names`` 后只接收指定 Worker 的结果

    ``worker_names`` 为 None 表示接收全部 Worker 的结果。已接收的结果通过可选的
    ``on_result`` 回调转交，响应器本身不累积结果，避免长期运行下无限增长。
    """

    def __init__(self):
        super().__init__("WaiterResultReactor")
        self._event_timeout = 0
        # 只接收这些 Worker 的结果；None 表示不过滤
        self.worker_names: list[str] | None = None
        # 可选的接收回调，签名为 (WorkerResult) -> None
        self.on_result = None
        self.set_event_callback(self._on_result)

    def accepts(self, result) -> bool:
        """判断该结果是否应被本响应器接收.

        Args:
            result: Worker 的执行结果

        Returns:
            是否接收
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
