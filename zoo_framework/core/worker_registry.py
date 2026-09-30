"""Worker 注册器 - 重构 Worker 注册机制.

P2 优化：重构 Worker 注册，支持更灵活的注册方式
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker


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
    """

    def __init__(self):
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
        # 1. 检查是否有实例
        if name in self._worker_instances:
            return self._worker_instances[name]

        # 2. 检查是否有工厂
        if name in self._worker_factories:
            instance = self._worker_factories[name]()
            self._worker_instances[name] = instance
            return instance

        # 3. 检查是否有类（延迟实例化）
        if name in self._worker_classes:
            instance = self._worker_classes[name]()
            self._worker_instances[name] = instance
            return instance

        return None

    def get_all_workers(self) -> dict[str, BaseWorker]:
        """获取所有 Worker 实例.

        自动实例化所有已注册但未实例化的 Worker

        Returns:
            Worker 字典
        """
        # 实例化所有延迟加载的 Worker
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
        # 如果存在实例，先销毁
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
        return self._worker_metadata.get(name)

    def get_workers_by_tag(self, tag: str) -> list[str]:
        """根据标签获取 Worker 名称列表.

        P2 优化：支持按标签筛选 Worker

        Args:
            tag: 标签

        Returns:
            Worker 名称列表
        """
        result = []
        for name, metadata in self._worker_metadata.items():
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
        result = []
        for name, metadata in self._worker_metadata.items():
            priority = metadata.get("priority", 0)
            if priority >= min_priority:
                result.append(name)
        return result


# 装饰器注册方式
def register_worker(name: str | None = None, metadata: dict | None = None):
    """Worker 注册装饰器.

    P2 优化：支持装饰器方式注册 Worker

    使用示例:
        @register_worker("my_worker", {"priority": 100})
        class MyWorker(BaseWorker):
            pass

    Args:
        name: Worker 名称，默认为类名
        metadata: 元数据
    """

    def decorator(cls):
        if not issubclass(cls, BaseWorker):
            raise TypeError(f"Must inherit from BaseWorker: {cls}")

        worker_name = name or cls.__name__

        # 注册到全局注册表
        from .aop import worker_register as registry

        if isinstance(registry, WorkerRegistry):
            registry.register_class(worker_name, cls, metadata)
        else:
            # 兼容旧版本
            instance = cls()
            registry.register(worker_name, instance)

        return cls

    return decorator


# 全局注册表
#
# 【已知欠债】这是**模块级隐式全局单例**、且持有进程级共享的 Worker 状态。按
# specs/scoped-container 的「框架自身的进程级共享 MUST 被显式归类」，它属于**尚未收编**
# 的容器外载体（同类的还有 EventReactorManager.reactor_map 与 EventChannelRegister._channel_map
# 两个类属性）。基线把它记为已知欠债、MUST NOT 被表述为已由容器归类。
# 收编它需要一个独立变更，且**类属性与实例的收编方式不同**（类属性没有实例身份）。
_global_registry: WorkerRegistry | None = None


def get_worker_registry() -> WorkerRegistry:
    """获取全局 Worker 注册表."""
    global _global_registry
    if _global_registry is None:
        _global_registry = WorkerRegistry()
    return _global_registry


# 导出公共 API
__all__ = [
    "WorkerRegistration",
    "WorkerRegistry",
    "get_worker_registry",
    "register_worker",
]
