"""base_worker - zoo_framework/workers/base_worker.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta
"""
import time

from zoo_framework.utils import LogUtils

from .worker_result import WorkerResult


class BaseWorker:
    """BaseWorker - 类功能描述"""

    def __init__(self, props: dict):
        self._props = props
        self.state = {}
        self._destroy_func = None
        self._on_create()
        self.num = 1

    def __del__(self):
        if self._destroy_func:
            self._destroy_func()

    def is_loop(self):
        if self._props.get("is_loop"):
            return self._props.get("is_loop")
        return False

    @property
    def run_timeout(self):
        return self._props.get("run_timeout")

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

    def run(self):
        result = {}
        try:
            LogUtils.info(f"{self.name} Worker is Start", self.__class__.__name__)
            result = self._execute()
            self._destroy_result(result)
            LogUtils.info(f"{self.name} Worker is Stop", self.__class__.__name__)
        except Exception as e:
            self._on_error()
            LogUtils.error(str(e), self.__class__.__name__)
        finally:
            self._on_done()

        if self._props.get("delay_time"):
            time.sleep(self._props["delay_time"])

        return WorkerResult(
            str(self.__class__.__name__).lower() + "_result", result, self.__class__.__name__
        )

    def _on_error(self):
        pass

    def _on_done(self):
        pass
