"""Plugin 系统 - 可扩展的插件架构.

Zoo Framework 插件系统允许开发者通过插件扩展框架功能。
每个插件都是一个独立的模块，可以在运行时动态加载。

使用示例:
    # 定义插件
    class MyPlugin(Plugin):
        name = "my_plugin"
        version = "1.0.0"

        def initialize(self, context):
            # 插件初始化逻辑
            pass

        def destroy(self):
            # 插件清理逻辑
            pass

    # 注册插件
    plugin_manager = PluginManager()
    plugin_manager.register(MyPlugin)

    # 使用插件
    plugin_manager.load_all()
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """插件基类.

    所有插件必须继承此类并实现抽象方法。

    Attributes:
        name: 插件名称，必须唯一
        version: 插件版本，遵循语义化版本规范
        description: 插件描述
        author: 插件作者
        dependencies: 插件依赖的其他插件列表
    """

    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    dependencies: list[str] = []

    def __init__(self):
        """初始化插件."""
        self._initialized = False
        self._context: Any | None = None

    @abstractmethod
    def initialize(self, context: Any) -> None:
        """初始化插件.

        插件被加载时会调用此方法。

        Args:
            context: 应用上下文，包含共享资源和配置
        """
        pass

    @abstractmethod
    def destroy(self) -> None:
        """销毁插件.

        插件被卸载或应用关闭时调用。
        应在此方法中释放资源。
        """
        pass

    @property
    def is_initialized(self) -> bool:
        """检查插件是否已初始化."""
        return self._initialized

    def _do_initialize(self, context: Any) -> None:
        """内部初始化方法."""
        if not self._initialized:
            self._context = context
            self.initialize(context)
            self._initialized = True
            logger.info(f"✅ Plugin '{self.name}' v{self.version} initialized")

    def _do_destroy(self) -> None:
        """内部销毁方法."""
        if self._initialized:
            self.destroy()
            self._initialized = False
            self._context = None
            logger.info(f"🛑 Plugin '{self.name}' destroyed")


class WorkerDelayManager:
    """Worker 延迟时间管理器.

    使用时间管理对象控制 Worker 的延迟执行。
    支持固定延迟、指数退避、自适应延迟等策略。

    Attributes:
        default_delay: 默认延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        min_delay: 最小延迟时间（秒）
    """

    def __init__(
        self, default_delay: float = 1.0, max_delay: float = 60.0, min_delay: float = 0.01
    ):
        self.default_delay = default_delay
        self.max_delay = max_delay
        self.min_delay = min_delay
        self._delays: dict[str, float] = {}
        self._last_execute_time: dict[str, float] = {}
        self._execute_count: dict[str, int] = {}

    def get_delay(self, worker_name: str) -> float:
        """获取 Worker 的延迟时间.

        Args:
            worker_name: Worker 名称

        Returns:
            延迟时间（秒）
        """
        return self._delays.get(worker_name, self.default_delay)

    def set_delay(self, worker_name: str, delay: float) -> None:
        """设置 Worker 的延迟时间.

        Args:
            worker_name: Worker 名称
            delay: 延迟时间（秒）
        """
        self._delays[worker_name] = max(self.min_delay, min(delay, self.max_delay))

    def record_execute(self, worker_name: str) -> None:
        """记录 Worker 执行时间.

        Args:
            worker_name: Worker 名称
        """
        import time

        self._last_execute_time[worker_name] = time.time()
        self._execute_count[worker_name] = self._execute_count.get(worker_name, 0) + 1

    def exponential_backoff(
        self, worker_name: str, base_delay: float = 1.0, max_retries: int = 5
    ) -> float:
        """指数退避延迟.

        当 Worker 执行失败时，使用指数退避策略增加延迟。

        Args:
            worker_name: Worker 名称
            base_delay: 基础延迟时间
            max_retries: 最大重试次数

        Returns:
            计算后的延迟时间
        """
        retry_count = self._execute_count.get(worker_name, 0)
        if retry_count > max_retries:
            retry_count = max_retries

        # 显式标注：mypy 把 `base_delay * (2**retry_count)` 推成 `Any`（已用 reveal_type 定位：
        # 两个操作数分别是 float 与 int，唯独乘积落到 Any），于是从声明返回 float 的函数里
        # 返回它就报 no-any-return。`delay: float` 是**算术上为真**的类型，此处补上它并不
        # 压制错误，而是把类型供给检查器。
        delay: float = base_delay * (2**retry_count)
        return min(delay, self.max_delay)

    def adaptive_delay(
        self, worker_name: str, execution_time: float, target_utilization: float = 0.8
    ) -> float:
        """自适应延迟.

        根据 Worker 执行时间动态调整延迟，以达到目标 CPU 利用率。

        Args:
            worker_name: Worker 名称
            execution_time: 上次执行耗时
            target_utilization: 目标 CPU 利用率

        Returns:
            调整后的延迟时间
        """
        if execution_time <= 0:
            return self.default_delay

        # 计算理想的延迟时间以达到目标利用率
        ideal_delay = execution_time * (1 / target_utilization - 1)

        # 平滑调整
        current_delay = self.get_delay(worker_name)
        new_delay = (current_delay * 0.7) + (ideal_delay * 0.3)

        self.set_delay(worker_name, new_delay)
        return new_delay

    def reset(self, worker_name: str) -> None:
        """重置 Worker 的延迟设置.

        Args:
            worker_name: Worker 名称
        """
        self._delays.pop(worker_name, None)
        self._last_execute_time.pop(worker_name, None)
        self._execute_count.pop(worker_name, None)


class PluginManager:
    """插件管理器.

    管理插件的注册、加载、卸载生命周期。

    提供方法：
    - register: 注册插件类
    - load / load_all: 加载插件
    - unload / unload_all: 卸载插件

    内部维护：
    - _plugins: 已注册的插件映射
    - _loaded_plugins: 当前已加载的插件实例映射
    """

    def __init__(self):
        self._plugins: dict[str, type[Plugin]] = {}
        self._loaded_plugins: dict[str, Plugin] = {}
        self._context: dict[str, Any] = {}
        self._delay_manager = WorkerDelayManager()

    @property
    def delay_manager(self) -> WorkerDelayManager:
        """获取延迟时间管理器."""
        return self._delay_manager

    def register(self, plugin_class: type[Plugin]) -> None:
        """注册插件.

        Args:
            plugin_class: 插件类，必须继承自 Plugin

        Raises:
            ValueError: 插件类无效或名称已存在
        """
        if not issubclass(plugin_class, Plugin):
            raise ValueError(f"Plugin class must inherit from Plugin: {plugin_class}")

        if not plugin_class.name:
            raise ValueError(f"Plugin must have a name: {plugin_class}")

        if plugin_class.name in self._plugins:
            logger.warning(f"Plugin '{plugin_class.name}' already registered, overwriting")

        self._plugins[plugin_class.name] = plugin_class
        logger.info(f"📦 Plugin '{plugin_class.name}' registered")

    def unregister(self, plugin_name: str) -> None:
        """注销插件.

        Args:
            plugin_name: 插件名称
        """
        if plugin_name in self._loaded_plugins:
            self.unload(plugin_name)

        self._plugins.pop(plugin_name, None)
        logger.info(f"🗑️ Plugin '{plugin_name}' unregistered")

    def load(self, plugin_name: str, context: Any | None = None) -> None:
        """加载单个插件.

        Args:
            plugin_name: 插件名称
            context: 应用上下文

        Raises:
            KeyError: 插件未注册
            RuntimeError: 依赖插件未加载
        """
        if plugin_name in self._loaded_plugins:
            logger.debug(f"Plugin '{plugin_name}' already loaded")
            return

        if plugin_name not in self._plugins:
            raise KeyError(f"Plugin not registered: {plugin_name}")

        plugin_class = self._plugins[plugin_name]

        # 检查依赖
        for dep in plugin_class.dependencies:
            if dep not in self._loaded_plugins:
                raise RuntimeError(f"Plugin '{plugin_name}' requires '{dep}' but it's not loaded")

        # 创建实例并初始化
        plugin = plugin_class()
        ctx = context or self._context
        plugin._do_initialize(ctx)

        self._loaded_plugins[plugin_name] = plugin
        logger.info(f"✅ Plugin '{plugin_name}' loaded")

    def load_all(self, context: Any | None = None) -> None:
        """加载所有已注册的插件.

        会自动处理插件依赖关系。

        Args:
            context: 应用上下文
        """
        # 按依赖顺序排序
        loaded = set(self._loaded_plugins.keys())
        to_load = set(self._plugins.keys()) - loaded

        while to_load:
            progress = False
            for name in list(to_load):
                plugin_class = self._plugins[name]
                deps = set(plugin_class.dependencies)

                if deps <= loaded:
                    self.load(name, context)
                    loaded.add(name)
                    to_load.remove(name)
                    progress = True

            if not progress and to_load:
                # 存在循环依赖
                raise RuntimeError(f"Circular dependency detected: {to_load}")

    def unload(self, plugin_name: str) -> None:
        """卸载插件.

        Args:
            plugin_name: 插件名称
        """
        if plugin_name not in self._loaded_plugins:
            return

        # 检查是否有其他插件依赖此插件
        for name, plugin in self._loaded_plugins.items():
            if name != plugin_name and plugin_name in self._plugins[name].dependencies:
                raise RuntimeError(f"Cannot unload '{plugin_name}', '{name}' depends on it")

        plugin = self._loaded_plugins.pop(plugin_name)
        plugin._do_destroy()
        logger.info(f"🛑 Plugin '{plugin_name}' unloaded")

    def unload_all(self) -> None:
        """卸载所有插件."""
        # 按依赖反向顺序卸载
        for name in list(self._loaded_plugins.keys()):
            self.unload(name)

    def get_plugin(self, plugin_name: str) -> Plugin | None:
        """获取已加载的插件实例.

        Args:
            plugin_name: 插件名称

        Returns:
            插件实例，如果未加载则返回 None
        """
        return self._loaded_plugins.get(plugin_name)

    def get_registered_plugins(self) -> list[str]:
        """获取所有已注册的插件名称."""
        return list(self._plugins.keys())

    def get_loaded_plugins(self) -> list[str]:
        """获取所有已加载的插件名称."""
        return list(self._loaded_plugins.keys())

    def set_context(self, key: str, value: Any) -> None:
        """设置全局上下文."""
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取全局上下文."""
        return self._context.get(key, default)


# 全局插件管理器实例
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """获取全局插件管理器实例."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def register_plugin(plugin_class: type[Plugin]) -> None:
    """便捷函数：注册插件到全局管理器."""
    get_plugin_manager().register(plugin_class)


def load_plugins(context: Any | None = None) -> None:
    """便捷函数：加载所有已注册的插件."""
    get_plugin_manager().load_all(context)


# 导出公共 API
__all__ = [
    "Plugin",
    "PluginManager",
    "WorkerDelayManager",
    "get_plugin_manager",
    "load_plugins",
    "register_plugin",
]
