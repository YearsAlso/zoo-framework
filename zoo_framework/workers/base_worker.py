import time

from zoo_framework.constant import WaiterConstant
from zoo_framework.utils import LogUtils

from .worker_result import WorkerResult


class BaseWorker:
    """Worker 基类。

    配置统一由 ``_props`` 字典承载；``is_loop`` / ``run_timeout`` / ``delay_time``
    均以属性形式暴露，读取时 MUST NOT 需要调用语法，子类 MUST NOT 用实例属性遮蔽它们。
    """

    def __init__(self, props: dict):
        self._props = props
        self.state = {}
        self._destroy_func = None
        self._on_create()
        self.num = 1

    def __del__(self):
        if self._destroy_func:
            self._destroy_func()

    @property
    def is_loop(self) -> bool:
        """是否在调度轮次之间保留并重复执行。

        ``_props`` 是唯一真源；未声明时视为不循环。
        """
        return bool(self._props.get("is_loop", False))

    @property
    def run_timeout(self):
        """本次执行的超时秒数；未声明时返回 None。"""
        return self._props.get("run_timeout")

    @property
    def delay_time(self) -> float:
        """单次执行结束后的等待秒数；未声明时视为不等待。"""
        return self._props.get("delay_time") or 0

    @property
    def name(self):
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
        """延迟等待。

        ``props`` 中的 ``sleep_func`` 可替换等待实现，使调度相关的用例无需真实等待。
        """
        sleep_func = self._props.get("sleep_func") or time.sleep
        sleep_func(seconds)

    def run(self):
        """执行一次。

        执行体抛出的异常在记录与调用 ``_on_error`` 之后**继续向上传播**，使调度器
        能够观测到失败并据此决定是否上报结果——静默吞掉异常会让失败伪装成"空结果"。

        Returns:
            WorkerResult: 本次执行的结果；执行失败时不返回（异常向上传播）
        """
        result = {}
        try:
            LogUtils.info(f"{self.name} Worker is Start", self.__class__.__name__)
            result = self._execute()
            self._destroy_result(result)
            LogUtils.info(f"{self.name} Worker is Stop", self.__class__.__name__)
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
