from typing import Any

from utils.thread_safe_dict import ThreadSafeDict


class WorkerRegister(object):
    """
    worker注册器
    """

    def __init__(self):
        self._worker_register = ThreadSafeDict()

    def register(self, key: str, value: Any):
        """
        注册worker
        """
        self._worker_register[key] = value

    def get_worker(self, key: str):
        """
        获得worker
        """
        return self._worker_register.get(key)

    def get_all_worker(self):
        """
        获得所有的worker
        """
        return self._worker_register.values()

    def unregister(self, key: str):
        """
        注销worker
        """
        self._worker_register.pop(key)
