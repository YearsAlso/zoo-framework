"""结构化日志配置.

P2: 可观测性提升 - 使用 structlog 实现结构化日志
"""
import logging
import sys
from typing import Any

# 尝试导入 structlog,如果不可用则回退到标准库
# 运行时安装: pip install structlog
try:
    import structlog  # type: ignore
except Exception:
    structlog = None
    STRUCTLOG_AVAILABLE = False
else:
    STRUCTLOG_AVAILABLE = True


class StructuredLogUtils:
    """结构化日志工具.

    P2 优化:提供 JSON 格式的结构化日志,便于日志收集和分析

    特性:
    - 结构化 JSON 日志输出
    - 自动上下文绑定
    - 性能指标自动收集
    - 支持日志级别动态调整
    """

    _instance: 'StructuredLogUtils | None' = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._logger = None
        self._context: dict[str, Any] = {}
        self._setup_logging()

    def _setup_logging(self) -> None:
        """配置日志系统."""
        if STRUCTLOG_AVAILABLE:
            self._setup_structlog()
        else:
            self._setup_standard_logging()

    def _setup_structlog(self) -> None:
        """配置 structlog."""
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),  # JSON 输出
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        self._logger = structlog.get_logger("zoo_framework")

    def _setup_standard_logging(self) -> None:
        """配置标准日志作为后备."""
        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            level=logging.INFO,
            stream=sys.stdout,
        )
        self._logger = logging.getLogger("zoo_framework")

    def bind(self, **context) -> "StructuredLogUtils":
        """绑定上下文变量.

        使用示例:
            log = StructuredLogUtils().bind(worker="StateMachineWorker", task_id="123")
            log.info("Task started")
            # 输出: {"event": "Task started", "worker": "StateMachineWorker", "task_id": "123"}

        Args:
            **context: 上下文键值对

        Returns:
            返回自身,支持链式调用
        """
        self._context.update(context)
        if STRUCTLOG_AVAILABLE and hasattr(self._logger, "bind"):
            self._logger = self._logger.bind(**context)
        return self

    def unbind(self, *keys) -> "StructuredLogUtils":
        """解绑上下文变量.

        Args:
            *keys: 要解绑的键名
        """
        for key in keys:
            self._context.pop(key, None)
        if STRUCTLOG_AVAILABLE and hasattr(self._logger, "unbind"):
            self._logger = self._logger.unbind(*keys)
        return self

    def debug(self, event: str, **kwargs) -> None:
        """DEBUG 级别日志."""
        self._log("debug", event, **kwargs)

    def info(self, event: str, **kwargs) -> None:
        """INFO 级别日志."""
        self._log("info", event, **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        """WARNING 级别日志."""
        self._log("warning", event, **kwargs)

    def error(self, event: str, **kwargs) -> None:
        """ERROR 级别日志."""
        self._log("error", event, **kwargs)

    def exception(self, event: str, **kwargs) -> None:
        """EXCEPTION 级别日志（包含异常信息）."""
        self._log("exception", event, **kwargs)

    def _log(self, level: str, event: str, **kwargs) -> None:
        """内部日志方法."""
        # 添加 emoji 标记
        emoji_map = {"debug": "🐛", "info": "ℹ️", "warning": "⚠️", "error": "❌", "exception": "💥"}

        # 添加 zoo 主题 emoji
        zoo_emojis = {"worker": "🦁", "cage": "🏠", "event": "🥘", "master": "👨‍🌾", "plugin": "🔌"}

        # 合并上下文
        log_data = {"event": event, "emoji": emoji_map.get(level, ""), **self._context, **kwargs}

        # 添加主题 emoji
        for key, emoji in zoo_emojis.items():
            if key in log_data:
                log_data[f"{key}_emoji"] = emoji

        # 记录日志
        logger_method = getattr(self._logger, level)
        if STRUCTLOG_AVAILABLE:
            logger_method(**log_data)
        else:
            # 标准库日志格式化
            extra = " ".join([f"{k}={v}" for k, v in log_data.items() if k != "event"])
            logger_method(f"{log_data.get('emoji', '')} {event} | {extra}")

    def metric(self, name: str, value: float, unit: str = "", **tags) -> None:
        """记录指标.

        P2: 可观测性 - 自动记录性能指标

        Args:
            name: 指标名称
            value: 指标值
            unit: 单位
            **tags: 标签
        """
        self.info(
            "metric_recorded",
            metric_name=name,
            metric_value=value,
            metric_unit=unit,
            metric_tags=tags,
        )


def get_logger(name: str | None = None) -> StructuredLogUtils:
    """获取结构化日志器.

    Args:
        name: 日志器名称

    Returns:
        结构化日志工具实例
    """
    logger = StructuredLogUtils()
    if name:
        logger.bind(logger_name=name)
    return logger


# 兼容性:保留旧的 LogUtils 接口
class LogUtilsCompatibility:
    """兼容旧版 LogUtils 接口."""

    _logger = None

    @classmethod
    def _get_logger(cls):
        if cls._logger is None:
            cls._logger = StructuredLogUtils()
        return cls._logger

    @classmethod
    def debug(cls, clazz, msg):
        cls._get_logger().debug(
            str(msg), class_name=clazz.__name__ if hasattr(clazz, "__name__") else str(clazz)
        )

    @classmethod
    def info(cls, clazz, msg):
        cls._get_logger().info(
            str(msg), class_name=clazz.__name__ if hasattr(clazz, "__name__") else str(clazz)
        )

    @classmethod
    def error(cls, clazz, msg):
        cls._get_logger().error(
            str(msg), class_name=clazz.__name__ if hasattr(clazz, "__name__") else str(clazz)
        )


# 导出
__all__ = [
    "LogUtilsCompatibility",
    "StructuredLogUtils",
    "get_logger",
]
