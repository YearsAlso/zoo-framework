from typing import Any

from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


class WorkerRegister:
    """The worker registrar."""

    def __init__(self) -> None:
        self._worker_register: ThreadSafeDict[str, Any] = ThreadSafeDict()

    def register(self, key: str, value: Any) -> None:
        """Register a worker."""
        self._worker_register[key] = value

    def get_worker(self, key: str) -> Any | None:
        """Get a worker."""
        return self._worker_register.get(key)

    def get_all_worker(self) -> list:
        """Get all workers."""
        return list(self._worker_register.values())

    def unregister(self, key: str) -> None:
        """Unregister a worker."""
        self._worker_register.pop(key)
