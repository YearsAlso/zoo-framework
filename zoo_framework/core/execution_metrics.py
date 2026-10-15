"""执行事实的观测接缝（变更 wire-svm-metrics / issue #246）。

**内核只生产事实、不决定去向**：每次执行在**唯一的结算收口**
（`WorkerDispatchCore.settle`）产出一条不可变的 `ExecutionFact`，交给一个可一次性
注册 / 注销的观察接缝。消费者（SVM 健康监控、可选 exporter）自行注册回调决定事实去
哪里；未注册任何回调时接缝是空操作，既有行为逐项不变。

形态与既有扩展点同构：对照 `StateMachineManager.observe_state` / `StateEffect`——
注册回调、注册表内部持有、触发时遍历调用。注册表本身是**进程级共享实例**（容器复位
即覆盖），不新增模块级可变容器，故无需在 `core/process_state.CARRIERS` 另开归类项。
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass

from zoo_framework.core.container import ThreadSafety, process_scoped
from zoo_framework.utils import LogUtils


@dataclass(frozen=True)
class ExecutionFact:
    """一次执行完成的**不可变**事实。

    不可变是硬性要求：可变对象经引用交给多个消费者会被就地改写，消费侧与断言都会读到
    最终态而非该次执行的取值（`.claude/rules/assertion-integrity.md`）。

    Attributes:
        worker_name: Worker 的注册身份（`BaseWorker.registry_name`）
        duration: 本次执行耗时（秒，由单调时钟测得）
        success: 是否成功（执行体未抛出异常）
    """

    worker_name: str
    duration: float
    success: bool


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class ExecutionObserverRegistry:
    """执行事实的观察接缝（进程级共享）。

    观察回调只增删一次、之后每次结算被遍历调用；内部列表由实例持有的 `RLock`
    自保护，故线程安全声明为 ``INSTANCE_GUARANTEED``。
    """

    def __init__(self) -> None:
        """Initialize the empty observer list and its lock."""
        self._observers: list[Callable[[ExecutionFact], None]] = []
        self._lock = threading.RLock()

    def observe(self, callback: Callable[[ExecutionFact], None]) -> None:
        """一次性注册一个观察回调。

        重复注册同一回调只保留一份（按相等去重，绑定方法同实例同函数视为同一份）。

        Args:
            callback: 收到每次执行事实的回调
        """
        with self._lock:
            if callback not in self._observers:
                self._observers.append(callback)

    def unobserve(self, callback: Callable[[ExecutionFact], None]) -> None:
        """注销一个观察回调；未注册过时为空操作。

        Args:
            callback: 之前注册过的回调
        """
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)

    def observers(self) -> tuple[Callable[[ExecutionFact], None], ...]:
        """当前观察回调的快照（诊断 / 断言用）。

        Returns:
            观察回调的元组快照
        """
        with self._lock:
            return tuple(self._observers)

    def emit(self, fact: ExecutionFact) -> None:
        """把一条执行事实交给全部观察回调。

        未注册任何回调时为空操作。单个回调抛出的异常 MUST NOT 拖垮调用侧的结算，也
        MUST NOT 阻止其余回调收到事实——按"大声失败、不静默降级"处理：记录错误日志后
        继续（不吞掉错误本身，它在日志里可见）。

        Args:
            fact: 本次执行的事实
        """
        with self._lock:
            observers = list(self._observers)

        for observer in observers:
            try:
                observer(fact)
            except Exception as e:
                LogUtils.error(
                    f"execution observer {observer!r} raised on worker '{fact.worker_name}': {e}",
                    self.__class__.__name__,
                )


def emit_execution_fact(worker_name: str, duration: float, success: bool) -> None:
    """把一次执行的事实交给进程级观察接缝（内核侧的发射入口）。

    Args:
        worker_name: Worker 的注册身份（`BaseWorker.registry_name`）
        duration: 本次执行耗时（秒）
        success: 是否成功
    """
    ExecutionObserverRegistry().emit(ExecutionFact(worker_name, duration, success))
