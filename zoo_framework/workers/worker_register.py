"""
worker_register - zoo_framework/workers/worker_register.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

from typing import Any

from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


class WorkerRegister:
    """worker注册器."""

    def __init__(self) -> None:
        self._worker_register: ThreadSafeDict = ThreadSafeDict()

    def register(self, key: str, value: Any) -> None:
        """注册worker."""
        self._worker_register[key] = value

    def get_worker(self, key: str) -> Any | None:
        """获得worker."""
        return self._worker_register.get(key)

    def get_all_worker(self) -> list:
        """获得所有的worker."""
        return list(self._worker_register.values())

    def unregister(self, key: str) -> None:
        """注销worker."""
        self._worker_register.pop(key)
