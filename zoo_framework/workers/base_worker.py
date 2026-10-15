import time
from typing import TYPE_CHECKING, Any

from zoo_framework.constant import WaiterConstant
from zoo_framework.utils import LogUtils

from .worker_result import WorkerResult

if TYPE_CHECKING:
    from collections.abc import Callable


class BaseWorker:
    """Worker base class.

    Configuration is carried uniformly by the ``_props`` dict; ``is_loop`` /
    ``run_timeout`` / ``delay_time`` are exposed as properties - reading them
    MUST NOT require call syntax, and subclasses MUST NOT shadow them with
    instance attributes.
    """

    def __init__(self, props: dict):
        self._props = props
        self.state: dict = {}
        # 注解为 Callable | None 而非让它被推断成 None：`__del__` 里那处真值判定正是
        # "它可能被赋成可调用对象"的证据。**但现状是全仓库没有任何地方给它赋值**，
        # 故那条销毁路径目前恒不执行——这是独立于类型的问题，已记为发现，见任务表 3.1。
        self._destroy_func: Callable | None = None
        self._on_create()
        self.num = 1

    def __del__(self):
        if self._destroy_func:
            self._destroy_func()

    @property
    def is_loop(self) -> bool:
        """Whether to keep this Worker across scheduling rounds and re-execute it.

        ``_props`` is the single source of truth; treated as non-looping when
        undeclared.
        """
        return bool(self._props.get("is_loop", False))

    @property
    def run_timeout(self):
        """Timeout in seconds for one execution; None when undeclared."""
        return self._props.get("run_timeout")

    @property
    def period(self):
        """Execution period in seconds.

        None when undeclared, meaning **event-driven** (every scheduling round
        counts as due). The period is declared per Worker and MUST NOT be
        pinned uniformly by the process or the scheduling model.
        """
        return self._props.get("period")

    @property
    def phase(self):
        """Period phase offset in seconds; 0.0 when undeclared.

        The offset of the first trigger relative to the schedule baseline, used
        to stagger the trigger moments of multiple periodic Workers.
        """
        return self._props.get("phase", 0.0)

    @property
    def delay_time(self) -> float:
        """Seconds to wait after each execution; treated as no wait when undeclared."""
        return self._props.get("delay_time") or 0

    @property
    def registry_name(self) -> str:
        """The suffix-free identity: configured name, or class name when undeclared.

        ``name`` is this identity plus the instance ordinal. A receiver
        filtering results by "which Worker" MUST match on this identity, since
        the ordinal is not known when the filter is declared (issue #229).
        """
        if self._props.get("name"):
            return str(self._props.get("name"))
        return str(self.__class__.__name__)

    @property
    def name(self):
        """Instance-unique name: the registry name plus the instance ordinal."""
        return f"{self.registry_name}_{self.num}"

    def _destroy_result(self, result):
        pass

    def _execute(self):
        pass

    def _on_create(self):
        pass

    def _wait(self, seconds: float) -> None:
        """Delayed wait.

        ``sleep_func`` in ``props`` can replace the wait implementation, so
        scheduling-related test cases need no real waiting.
        """
        sleep_func = self._props.get("sleep_func") or time.sleep
        sleep_func(seconds)

    def build_result(self, result: Any, error: BaseException | None = None) -> WorkerResult:
        """由已得值产出结果（共用入口）。

        ``run()``（线程 / 线程池模型，同步驱动执行体）与模型托管路径（常驻事件循环
        模型在循环线程上驱动协程）共用这一份结果契约：``WorkerResult`` 的构造与 #228
        的失败标记是唯一实现，避免两条路径各写一份而漂移。运行标识（``run_id`` /
        ``session_id``）由结算侧（``WorkerDispatchCore.settle``）按登记项统一盖章，
        此处不填。

        Args:
            result: 执行体的产出值；失败时为 None
            error: 执行体抛出的异常；成功时为 None

        Returns:
            WorkerResult: 失败时 content 为 None 且 ``error`` 携带原因；成功时
                携带产出值
        """
        if error is not None:
            return WorkerResult(
                WaiterConstant.WORKER_RESULT_TOPIC,
                None,
                self.__class__.__name__,
                worker_name=self.name,
                registry_name=self.registry_name,
                error=f"{type(error).__name__}: {error}",
            )

        return WorkerResult(
            WaiterConstant.WORKER_RESULT_TOPIC,
            result,
            self.__class__.__name__,
            worker_name=self.name,
            registry_name=self.registry_name,
        )

    def run(self) -> WorkerResult:
        """Execute once.

        A failure is **reported, not left implicit** (issue #228): the result
        topic is how consumers observe that a Worker finished, so an execution
        body raising MUST still produce one result carrying the failure. The
        returned result is marked as a failure (``error`` set, ``success``
        false, content None) so consumers can tell "failed" apart from "still
        running"; the failure MUST NOT be delivered in the shape of a
        successful empty result. The error is logged and ``_on_error`` /
        ``_on_done`` still run, exactly as before.

        Returns:
            WorkerResult: The result of this execution. On failure the content
                is None and ``error`` carries the reason.
        """
        result: Any = {}
        error: Exception | None = None
        try:
            # 每轮进入/退出是框架自己的心跳，默认级别下不输出（log.level=debug 可见）
            LogUtils.debug(f"{self.name} Worker is Start", self.__class__.__name__)
            result = self._execute()
            self._destroy_result(result)
            LogUtils.debug(f"{self.name} Worker is Stop", self.__class__.__name__)
        except Exception as e:
            error = e
            self._on_error()
            LogUtils.error(str(e), self.__class__.__name__)
        finally:
            self._on_done()

        if error is not None:
            # 失败也产生一条结果（#228）：消费者靠结果主题判断"跑完没有"，
            # 只写日志的失败会被当成"仍在执行"（Worker 已不在调度表里，却永远
            # 等不到结果）。失败结果携带 error 标记，MUST NOT 冒充成功空结果。
            # 不写 _destroy_result：失败没有产出可销毁的结果。
            return self.build_result(None, error)

        if self.delay_time:
            self._wait(self.delay_time)

        return self.build_result(result)

    def _on_error(self):
        pass

    def _on_done(self):
        pass
