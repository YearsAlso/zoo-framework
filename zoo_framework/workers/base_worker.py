import time
from typing import TYPE_CHECKING

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
    def name(self):
        """Instance-unique name: the configured name or class name plus the instance number."""
        if self._props.get("name"):
            return str(self._props.get("name")) + "_" + str(self.num)
        return str(self.__class__.__name__) + "_" + str(self.num)

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

    def run(self):
        """Execute once.

        An exception raised by the execution body **keeps propagating upward**
        after being logged and after ``_on_error`` is called, so the scheduler
        can observe the failure and decide whether to report the result -
        silently swallowing the exception would disguise the failure as an
        "empty result".

        Returns:
            WorkerResult: The result of this execution; not returned on failure
                (the exception propagates).
        """
        result = {}
        try:
            # 每轮进入/退出是框架自己的心跳，默认级别下不输出（log.level=debug 可见）
            LogUtils.debug(f"{self.name} Worker is Start", self.__class__.__name__)
            result = self._execute()
            self._destroy_result(result)
            LogUtils.debug(f"{self.name} Worker is Stop", self.__class__.__name__)
        except Exception as e:
            self._on_error()
            LogUtils.error(str(e), self.__class__.__name__)
            raise
        finally:
            self._on_done()

        if self.delay_time:
            self._wait(self.delay_time)

        return WorkerResult(
            WaiterConstant.WORKER_RESULT_TOPIC,
            result,
            self.__class__.__name__,
            worker_name=self.name,
        )

    def _on_error(self):
        pass

    def _on_done(self):
        pass
