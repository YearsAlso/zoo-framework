import ctypes
import threading

from zoo_framework.utils import LogUtils


class ZooThread(threading.Thread):
    def __init__(self, name):
        threading.Thread.__init__(self)
        self.name = name

    def run(self):
        # target function of the thread class
        try:  # try/finally handles the exception to kill the thread
            while True:
                LogUtils.debug("running " + self.name)
        finally:
            LogUtils.debug("ended")

    def get_id(self):
        # returns id of the respective thread
        if hasattr(self, "_thread_id"):
            return self._thread_id
        # `_active` is a CPython private implementation detail (not declared
        # in typeshed), so take it via getattr rather than papering over with
        # an ignore directive - the latter would hide that fact.
        for id, thread in getattr(threading, "_active", {}).items():
            if thread is self:
                return id
        return None

    def raise_exception(self):
        """Raise the exception."""
        thread_id = self.get_id()
        # The essence is this line: send the thread an exception, and the
        # thread stops on the other side once it responds
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print("Exception raise failure")
