"""Plugin system - an extensible plugin architecture.

The Zoo Framework plugin system lets developers extend framework behavior via
plugins. Each plugin is an independent module that can be loaded dynamically at
runtime.

Example:
    # Define a plugin
    class MyPlugin(Plugin):
        name = "my_plugin"
        version = "1.0.0"

        def initialize(self, context):
            # plugin initialization logic
            pass

        def destroy(self):
            # plugin cleanup logic
            pass

    # Register the plugin
    plugin_manager = PluginManager()
    plugin_manager.register(MyPlugin)

    # Use the plugin
    plugin_manager.load_all()
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Plugin base class.

    Every plugin must inherit from this class and implement the abstract
    methods.

    Attributes:
        name: Plugin name; must be unique.
        version: Plugin version, following semantic versioning.
        description: Plugin description.
        author: Plugin author.
        dependencies: Other plugins this one depends on.
    """

    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    dependencies: list[str] = []

    def __init__(self):
        """Initialize the plugin."""
        self._initialized = False
        self._context: Any | None = None

    @abstractmethod
    def initialize(self, context: Any) -> None:
        """Initialize the plugin.

        Called when the plugin is loaded.

        Args:
            context: Application context with shared resources and configuration.
        """
        pass

    @abstractmethod
    def destroy(self) -> None:
        """Destroy the plugin.

        Called when the plugin is unloaded or the application shuts down.
        Release resources here.
        """
        pass

    @property
    def is_initialized(self) -> bool:
        """Whether the plugin has been initialized."""
        return self._initialized

    def _do_initialize(self, context: Any) -> None:
        """Internal initialization."""
        if not self._initialized:
            self._context = context
            self.initialize(context)
            self._initialized = True
            logger.info(f"✅ Plugin '{self.name}' v{self.version} initialized")

    def _do_destroy(self) -> None:
        """Internal teardown."""
        if self._initialized:
            self.destroy()
            self._initialized = False
            self._context = None
            logger.info(f"🛑 Plugin '{self.name}' destroyed")


class WorkerDelayManager:
    """Worker delay-time manager.

    Controls a Worker's delayed execution via a delay-strategy object. Supports
    fixed delay, exponential backoff, adaptive delay, and other strategies.

    Attributes:
        default_delay: Default delay in seconds.
        max_delay: Maximum delay in seconds.
        min_delay: Minimum delay in seconds.
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
        """Get a Worker's delay.

        Args:
            worker_name: Worker name.

        Returns:
            The delay in seconds.
        """
        return self._delays.get(worker_name, self.default_delay)

    def set_delay(self, worker_name: str, delay: float) -> None:
        """Set a Worker's delay.

        Args:
            worker_name: Worker name.
            delay: The delay in seconds.
        """
        self._delays[worker_name] = max(self.min_delay, min(delay, self.max_delay))

    def record_execute(self, worker_name: str) -> None:
        """Record a Worker execution.

        Args:
            worker_name: Worker name.
        """
        import time

        self._last_execute_time[worker_name] = time.time()
        self._execute_count[worker_name] = self._execute_count.get(worker_name, 0) + 1

    def exponential_backoff(
        self, worker_name: str, base_delay: float = 1.0, max_retries: int = 5
    ) -> float:
        """Exponential backoff delay.

        When a Worker's execution fails, grow the delay exponentially.

        Args:
            worker_name: Worker name.
            base_delay: Base delay.
            max_retries: Maximum retry count.

        Returns:
            The computed delay.
        """
        retry_count = self._execute_count.get(worker_name, 0)
        if retry_count > max_retries:
            retry_count = max_retries

        # Explicit annotation: mypy infers `base_delay * (2**retry_count)` as `Any`
        # (located via reveal_type: the operands are float and int, only the
        # product falls to Any), so returning it from a function declared to
        # return float trips no-any-return. `delay: float` is arithmetically
        # true - this supplies the type to the checker rather than suppressing
        # the error.
        delay: float = base_delay * (2**retry_count)
        return min(delay, self.max_delay)

    def adaptive_delay(
        self, worker_name: str, execution_time: float, target_utilization: float = 0.8
    ) -> float:
        """Adaptive delay.

        Adjusts the delay based on the Worker's last execution time to approach
        the target CPU utilization.

        Args:
            worker_name: Worker name.
            execution_time: Duration of the last execution.
            target_utilization: Target CPU utilization.

        Returns:
            The adjusted delay.
        """
        if execution_time <= 0:
            return self.default_delay

        # Ideal delay for the target utilization
        ideal_delay = execution_time * (1 / target_utilization - 1)

        # Smooth adjustment
        current_delay = self.get_delay(worker_name)
        new_delay = (current_delay * 0.7) + (ideal_delay * 0.3)

        self.set_delay(worker_name, new_delay)
        return new_delay

    def reset(self, worker_name: str) -> None:
        """Reset a Worker's delay settings.

        Args:
            worker_name: Worker name.
        """
        self._delays.pop(worker_name, None)
        self._last_execute_time.pop(worker_name, None)
        self._execute_count.pop(worker_name, None)


class PluginManager:
    """Plugin manager.

    Manages the register / load / unload lifecycle of plugins.

    Provides:
    - register: register a plugin class
    - load / load_all: load plugins
    - unload / unload_all: unload plugins

    Maintains internally:
    - _plugins: mapping of registered plugins
    - _loaded_plugins: mapping of currently loaded plugin instances
    """

    def __init__(self):
        self._plugins: dict[str, type[Plugin]] = {}
        self._loaded_plugins: dict[str, Plugin] = {}
        self._context: dict[str, Any] = {}
        self._delay_manager = WorkerDelayManager()

    @property
    def delay_manager(self) -> WorkerDelayManager:
        """The delay-time manager."""
        return self._delay_manager

    def register(self, plugin_class: type[Plugin]) -> None:
        """Register a plugin.

        Args:
            plugin_class: The plugin class; must inherit from Plugin.

        Raises:
            ValueError: The plugin class is invalid or the name already exists.
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
        """Unregister a plugin.

        Args:
            plugin_name: Plugin name.
        """
        if plugin_name in self._loaded_plugins:
            self.unload(plugin_name)

        self._plugins.pop(plugin_name, None)
        logger.info(f"🗑️ Plugin '{plugin_name}' unregistered")

    def load(self, plugin_name: str, context: Any | None = None) -> None:
        """Load a single plugin.

        Args:
            plugin_name: Plugin name.
            context: Application context.

        Raises:
            KeyError: The plugin is not registered.
            RuntimeError: A dependency plugin is not loaded.
        """
        if plugin_name in self._loaded_plugins:
            logger.debug(f"Plugin '{plugin_name}' already loaded")
            return

        if plugin_name not in self._plugins:
            raise KeyError(f"Plugin not registered: {plugin_name}")

        plugin_class = self._plugins[plugin_name]

        # Check dependencies
        for dep in plugin_class.dependencies:
            if dep not in self._loaded_plugins:
                raise RuntimeError(f"Plugin '{plugin_name}' requires '{dep}' but it's not loaded")

        # Instantiate and initialize
        plugin = plugin_class()
        ctx = context or self._context
        plugin._do_initialize(ctx)

        self._loaded_plugins[plugin_name] = plugin
        logger.info(f"✅ Plugin '{plugin_name}' loaded")

    def load_all(self, context: Any | None = None) -> None:
        """Load all registered plugins.

        Plugin dependencies are resolved automatically.

        Args:
            context: Application context.
        """
        # Order by dependencies
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
                # Circular dependency
                raise RuntimeError(f"Circular dependency detected: {to_load}")

    def unload(self, plugin_name: str) -> None:
        """Unload a plugin.

        Args:
            plugin_name: Plugin name.
        """
        if plugin_name not in self._loaded_plugins:
            return

        # Check whether other plugins depend on this one
        for name, plugin in self._loaded_plugins.items():
            if name != plugin_name and plugin_name in self._plugins[name].dependencies:
                raise RuntimeError(f"Cannot unload '{plugin_name}', '{name}' depends on it")

        plugin = self._loaded_plugins.pop(plugin_name)
        plugin._do_destroy()
        logger.info(f"🛑 Plugin '{plugin_name}' unloaded")

    def unload_all(self) -> None:
        """Unload all plugins."""
        # Unload in reverse dependency order
        for name in list(self._loaded_plugins.keys()):
            self.unload(name)

    def get_plugin(self, plugin_name: str) -> Plugin | None:
        """Get a loaded plugin instance.

        Args:
            plugin_name: Plugin name.

        Returns:
            The plugin instance, or None if not loaded.
        """
        return self._loaded_plugins.get(plugin_name)

    def get_registered_plugins(self) -> list[str]:
        """Get all registered plugin names."""
        return list(self._plugins.keys())

    def get_loaded_plugins(self) -> list[str]:
        """Get all loaded plugin names."""
        return list(self._loaded_plugins.keys())

    def set_context(self, key: str, value: Any) -> None:
        """Set a global context value."""
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a global context value."""
        return self._context.get(key, default)


# Global plugin manager instance
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def register_plugin(plugin_class: type[Plugin]) -> None:
    """Convenience wrapper: register a plugin with the global manager."""
    get_plugin_manager().register(plugin_class)


def load_plugins(context: Any | None = None) -> None:
    """Convenience wrapper: load all registered plugins."""
    get_plugin_manager().load_all(context)


# Public API exports
__all__ = [
    "Plugin",
    "PluginManager",
    "WorkerDelayManager",
    "get_plugin_manager",
    "load_plugins",
    "register_plugin",
]
