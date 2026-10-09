"""Worker registry - reworked Worker registration mechanism.

P2 optimization: rework Worker registration to support more flexible registration styles.
"""

import inspect
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from zoo_framework.core.container import ThreadSafety, process_instance, register_process_instance
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker


def _requires_constructor_args(cls: type) -> bool:
    """Whether the class **must** be constructed with arguments - the premise for lazy instantiation (a no-arg call) to hold.

    The lazy instantiation path calls `cls()` with no arguments, so
    "constructible without arguments" is its implicit premise. That premise
    used to be unchecked: registering a class that requires arguments
    (`BaseWorker` itself is one) sailed through registration and only raised
    `TypeError` at first instantiation. This turns the implicit premise into a
    condition checked at **registration time**.
    """
    try:
        # 读 `cls.__init__` 会被判"不健全"（子类的 __init__ 可能与基类签名不兼容）——
        # 而本函数**正是**要检查各家签名，故这个不健全是它要处理的对象而非要避免的。
        parameters = inspect.signature(cls.__init__).parameters  # type: ignore[misc]
    except (TypeError, ValueError):  # 内建/无法取签名者，按下不拦
        return False
    return any(
        parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        for name, parameter in parameters.items()
        if name != "self"
    )


class WorkerRegistration(ABC):
    """Worker registration abstract base class.

    P2 optimization: define the Worker registration interface.
    """

    @abstractmethod
    def register(self, name: str, worker_class: type[BaseWorker]) -> None:
        """Register a Worker."""
        pass

    @abstractmethod
    def get_worker(self, name: str) -> Any | None:
        """Get the Worker instance."""
        pass

    @abstractmethod
    def get_all_workers(self) -> dict[str, BaseWorker]:
        """Get all Workers."""
        pass


class WorkerRegistry:
    """Worker registry.

    P2 optimization: rework the Worker registration mechanism to support:
    - class registration and instance registration
    - decorator registration
    - lazy instantiation
    - dependency injection

    Thread-safety ownership (the premise of being absorbed in change
    absorb-debt-carriers / #50): all read-modify-writes are protected by one
    reentrant lock in the instance, so the `INSTANCE_GUARANTEED` declaration
    is honest; the four bare dicts previously had no self-protection under
    concurrent registration and dispatch at runtime.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._worker_classes: dict[str, type[BaseWorker]] = {}
        self._worker_instances: dict[str, BaseWorker] = {}
        self._worker_factories: dict[str, Callable[[], BaseWorker]] = {}
        self._worker_metadata: dict[str, dict] = {}

    def register_class(
        self, name: str, worker_class: type[BaseWorker], metadata: dict | None = None
    ) -> None:
        """Register a Worker class (lazy instantiation).

        P2 optimization: support lazy instantiation to save resources.

        Args:
            name: the Worker name
            worker_class: the Worker class
            metadata: metadata (priority, tags, etc.)
        """
        if not issubclass(worker_class, BaseWorker):
            raise TypeError(f"Must inherit from BaseWorker: {worker_class}")

        # 延迟实例化会无参调用该类，故在此拒绝"必须带参构造"的类——否则这个错误会推迟到
        # 第一次实例化时才以 TypeError 暴露（BaseWorker 本身就是这种类）。
        if _requires_constructor_args(worker_class):
            raise TypeError(
                f"{worker_class} requires constructor arguments and cannot be lazily instantiated;"
                f"use register_instance or register_factory instead"
            )

        with self._lock:
            self._worker_classes[name] = worker_class
            self._worker_metadata[name] = metadata or {}
        LogUtils.info(f"📦 Worker class '{name}' registered")

    def register_instance(
        self, name: str, worker_instance: BaseWorker, metadata: dict | None = None
    ) -> None:
        """Register a Worker instance.

        Args:
            name: the Worker name
            worker_instance: the Worker instance
            metadata: metadata
        """
        if not isinstance(worker_instance, BaseWorker):
            raise TypeError(f"Must be BaseWorker instance: {worker_instance}")

        with self._lock:
            self._worker_instances[name] = worker_instance
            self._worker_metadata[name] = metadata or {}
        LogUtils.info(f"✅ Worker instance '{name}' registered")

    def register_factory(
        self, name: str, factory: Callable[[], BaseWorker], metadata: dict | None = None
    ) -> None:
        """Register a Worker factory function.

        P2 optimization: support creating Workers via the factory pattern.

        Args:
            name: the Worker name
            factory: the factory function
            metadata: metadata
        """
        with self._lock:
            self._worker_factories[name] = factory
            self._worker_metadata[name] = metadata or {}
        LogUtils.info(f"🏭 Worker factory '{name}' registered")

    def get_worker(self, name: str) -> Any | None:
        """Get a Worker instance.

        Lookup order: instance -> factory -> class.

        Args:
            name: the Worker name

        Returns:
            The Worker instance
        """
        # 1. 检查是否有实例（读-改-写全程持锁；可重入，内部不回调外部代码）
        with self._lock:
            if name in self._worker_instances:
                return self._worker_instances[name]

            # 2. 检查是否有工厂
            if name in self._worker_factories:
                instance = self._worker_factories[name]()
                self._worker_instances[name] = instance
                return instance

            # 3. 检查是否有类（延迟实例化）
            if name in self._worker_classes:
                # mypy 看不到 register_class 里的注册期校验，故此处仍需定向 ignore —— 它压制的
                # 是一条**已在注册期强制**的前提，不是未经验证的假设。
                instance = self._worker_classes[name]()  # type: ignore[call-arg]
                self._worker_instances[name] = instance
                return instance

            return None

    def get_all_workers(self) -> dict[str, BaseWorker]:
        """Get all Worker instances.

        Automatically instantiates every registered-but-not-instantiated
        Worker.

        Returns:
            The Worker dict
        """
        # 实例化所有延迟加载的 Worker（持锁；get_worker 同线程重入）
        with self._lock:
            for name in list(self._worker_classes.keys()):
                if name not in self._worker_instances:
                    self.get_worker(name)

            for name in list(self._worker_factories.keys()):
                if name not in self._worker_instances:
                    self.get_worker(name)

            return self._worker_instances.copy()

    def unregister(self, name: str) -> None:
        """Unregister a Worker.

        Args:
            name: the Worker name
        """
        # 如果存在实例，先销毁（持锁；_destroy 为用户钩子，同线程重入安全由 RLock 保证）
        with self._lock:
            if name in self._worker_instances:
                worker = self._worker_instances[name]
                if hasattr(worker, "_destroy"):
                    worker._destroy(None)

            self._worker_classes.pop(name, None)
            self._worker_instances.pop(name, None)
            self._worker_factories.pop(name, None)
            self._worker_metadata.pop(name, None)
        LogUtils.info(f"🗑️ Worker '{name}' unregistered")

    def get_metadata(self, name: str) -> dict | None:
        """Get the Worker metadata.

        Args:
            name: the Worker name

        Returns:
            The metadata dict
        """
        with self._lock:
            return self._worker_metadata.get(name)

    def get_workers_by_tag(self, tag: str) -> list[str]:
        """Get Worker names by tag.

        P2 optimization: support filtering Workers by tag.

        Args:
            tag: the tag

        Returns:
            The Worker name list
        """
        with self._lock:
            snapshot = list(self._worker_metadata.items())
        result = []
        for name, metadata in snapshot:
            tags = metadata.get("tags", [])
            if tag in tags:
                result.append(name)
        return result

    def get_workers_by_priority(self, min_priority: int) -> list[str]:
        """Get Worker names by priority.

        Args:
            min_priority: the minimum priority

        Returns:
            The Worker name list
        """
        with self._lock:
            snapshot = list(self._worker_metadata.items())
        result = []
        for name, metadata in snapshot:
            priority = metadata.get("priority", 0)
            if priority >= min_priority:
                result.append(name)
        return result


# 已删除（变更 cleanup-aop-public-surface / issue #49）：`register_worker` 装饰器的
# `isinstance(registry, WorkerRegistry)` 判定恒为 False（它拿的是 legacy
# `WorkerRegister` 实例），实际只走"写入不被派发的表"的分支——零使用、死分支，
# 与 `Master.register_worker` 又构成第二条注册真源，故整删而非修复。


# 全局注册表（变更 absorb-debt-carriers / #50 交付 1，方案 A）：原模块级隐式单例
# `_global_registry` 已收编进框架进程级容器——`get_worker_registry()` 解析容器项，
# 复位统一走 `framework_container().reset()`，不再有第二套手工清表路径。
# 直接 `WorkerRegistry()` 构造**不受影响**（仍可建私有实例）；只有进程级入口
# 经容器。未加 @process_scoped 正是因为这条区分：装饰器会把**所有** `cls()`
# 构造都变成单例，改变测试/局部注册表的既有语义。
register_process_instance(WorkerRegistry, thread_safety=ThreadSafety.INSTANCE_GUARANTEED)


def get_worker_registry() -> WorkerRegistry:
    """Get the process-level Worker registry (the single instance in the framework container)."""
    # 容器按 WorkerRegistry 注册（工厂即类本身），解析结果必为本类实例；
    # 压制的是 resolve 的 Any 签名，不是未验证的假设。
    return process_instance(WorkerRegistry)  # type: ignore[no-any-return]


# 导出公共 API
__all__ = [
    "WorkerRegistration",
    "WorkerRegistry",
    "get_worker_registry",
]
