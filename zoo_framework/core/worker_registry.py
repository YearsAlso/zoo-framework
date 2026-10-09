"""Worker 注册器 - 重构 Worker 注册机制.

P2 优化：重构 Worker 注册，支持更灵活的注册方式
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
    """该类是否**必须**带参构造——延迟实例化（无参调用）的前提是否成立.

    延迟实例化路径会 `cls()` 无参调用，故"可无参构造"是它的隐含前提。原先这个前提
    无人校验：注册一个必须带参的类（`BaseWorker` 本身就是）会一路通过注册，
    直到第一次实例化才抛 `TypeError`。此处把隐含前提变成**注册期可校验**的条件。
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
    """Worker 注册抽象基类.

    P2 优化：定义 Worker 注册的接口
    """

    @abstractmethod
    def register(self, name: str, worker_class: type[BaseWorker]) -> None:
        """注册 Worker."""
        pass

    @abstractmethod
    def get_worker(self, name: str) -> Any | None:
        """获取 Worker 实例."""
        pass

    @abstractmethod
    def get_all_workers(self) -> dict[str, BaseWorker]:
        """获取所有 Worker."""
        pass


class WorkerRegistry:
    """Worker 注册表.

    P2 优化：重构 Worker 注册机制，支持：
    - 类注册和实例注册
    - 装饰器注册
    - 延迟实例化
    - 依赖注入

    线程安全归属（变更 absorb-debt-carriers / #50 收编的前提）：全部读-改-写由实例
    内一把可重入锁保护，`INSTANCE_GUARANTEED` 声明如实；此前四张裸 dict 在
    运行期注册与派发并发访问下并无自保。
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
        """注册 Worker 类（延迟实例化）.

        P2 优化：支持延迟实例化，节省资源

        Args:
            name: Worker 名称
            worker_class: Worker 类
            metadata: 元数据（优先级、标签等）
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
        """注册 Worker 实例.

        Args:
            name: Worker 名称
            worker_instance: Worker 实例
            metadata: 元数据
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
        """注册 Worker 工厂函数.

        P2 优化：支持工厂模式创建 Worker

        Args:
            name: Worker 名称
            factory: 工厂函数
            metadata: 元数据
        """
        with self._lock:
            self._worker_factories[name] = factory
            self._worker_metadata[name] = metadata or {}
        LogUtils.info(f"🏭 Worker factory '{name}' registered")

    def get_worker(self, name: str) -> Any | None:
        """获取 Worker 实例.

        按优先级查找：实例 -> 工厂 -> 类

        Args:
            name: Worker 名称

        Returns:
            Worker 实例
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
        """获取所有 Worker 实例.

        自动实例化所有已注册但未实例化的 Worker

        Returns:
            Worker 字典
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
        """注销 Worker.

        Args:
            name: Worker 名称
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
        """获取 Worker 元数据.

        Args:
            name: Worker 名称

        Returns:
            元数据字典
        """
        with self._lock:
            return self._worker_metadata.get(name)

    def get_workers_by_tag(self, tag: str) -> list[str]:
        """根据标签获取 Worker 名称列表.

        P2 优化：支持按标签筛选 Worker

        Args:
            tag: 标签

        Returns:
            Worker 名称列表
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
        """根据优先级获取 Worker 名称列表.

        Args:
            min_priority: 最小优先级

        Returns:
            Worker 名称列表
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
    """获取进程级 Worker 注册表（框架容器内的唯一实例）."""
    # 容器按 WorkerRegistry 注册（工厂即类本身），解析结果必为本类实例；
    # 压制的是 resolve 的 Any 签名，不是未验证的假设。
    return process_instance(WorkerRegistry)  # type: ignore[no-any-return]


# 导出公共 API
__all__ = [
    "WorkerRegistration",
    "WorkerRegistry",
    "get_worker_registry",
]
