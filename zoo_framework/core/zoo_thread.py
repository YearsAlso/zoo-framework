"""zoo_thread - zoo_framework/core/zoo_thread.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta
"""

import ctypes
import threading

from zoo_framework.utils import LogUtils


class ZooThread(threading.Thread):
    """ZooThread - 类功能描述"""
    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name

    def run(self):
        # target function of the thread class
        try:  # 用try/finally 的方式处理exception,从而kill thread
            while True:
                LogUtils.debug("running " + self.name)
        finally:
            LogUtils.debug("ended")

    def get_id(self):
        # returns id of the respective thread
        if hasattr(self, "_thread_id"):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id
        return None

    def raise_exception(self):
        """引发异常."""
        thread_id = self.get_id()
        # 精髓就是这句话,给线程发过去一个exceptions,线程就那边响应完就停了
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print("Exception raise failure")

