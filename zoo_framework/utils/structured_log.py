"""Structured log configuration.

P2: observability improvement - structured logging via structlog.
"""

import logging
import sys
from typing import Any

from .log_utils import SafeStreamHandler

# Try importing structlog; fall back to the standard library if unavailable.
# Install at runtime: pip install structlog
try:
    import structlog
except Exception:
    structlog = None
    STRUCTLOG_AVAILABLE = False
else:
    STRUCTLOG_AVAILABLE = True


class StructuredLogUtils:
    """Structured log utility.

    P2 optimization: JSON-formatted structured logs, easing log collection
    and analysis.

    Features:
    - structured JSON log output
    - automatic context binding
    - automatic performance metric collection
    - dynamic log-level adjustment
    """

    _instance: "StructuredLogUtils | None" = None
    _initialized = False
    # Declared as Any: when structlog is available it is a BoundLogger, when
    # not it is a standard-library Logger; the only common ground of the two
    # paths is having debug/info/... methods, and any concrete type would
    # exclude the other path.
    _logger: Any = None

    def __new__(cls) -> "StructuredLogUtils":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._initialized = True
        self._logger = None
        self._context: dict[str, Any] = {}
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure the logging system."""
        if STRUCTLOG_AVAILABLE:
            self._setup_structlog()
        else:
            self._setup_standard_logging()

    def _setup_structlog(self) -> None:
        """Configure structlog."""
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
                structlog.processors.JSONRenderer(),  # JSON output
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        self._logger = structlog.get_logger("zoo_framework")

    def _setup_standard_logging(self) -> None:
        """Configure standard logging as the fallback.

        Console output uses SafeStreamHandler: on a non-UTF-8 console the
        worst case is glyph degradation of non-ASCII characters; it MUST NOT
        be the whole log line vanishing together with the timestamp.
        """
        handler = SafeStreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler])
        self._logger = logging.getLogger("zoo_framework")

    def bind(self, **context: Any) -> "StructuredLogUtils":
        """Bind context variables.

        Usage example:
            log = StructuredLogUtils().bind(worker="StateMachineWorker", task_id="123")
            log.info("Task started")
            # output: {"event": "Task started", "worker": "StateMachineWorker", "task_id": "123"}

        Args:
            **context: the context key-value pairs

        Returns:
            Itself, supporting chained calls
        """
        self._context.update(context)
        # An explicit `is not None`: hasattr(None, "bind") is already False at
        # runtime, so behavior is unchanged; but static checking cannot narrow
        # `Any | None` from hasattr, so the added None check only makes this
        # existing guard visible.
        if STRUCTLOG_AVAILABLE and self._logger is not None and hasattr(self._logger, "bind"):
            self._logger = self._logger.bind(**context)
        return self

    def unbind(self, *keys: str) -> "StructuredLogUtils":
        """Unbind context variables.

        Args:
            *keys: the key names to unbind
        """
        for key in keys:
            self._context.pop(key, None)
        if STRUCTLOG_AVAILABLE and self._logger is not None and hasattr(self._logger, "unbind"):
            self._logger = self._logger.unbind(*keys)
        return self

    def debug(self, event: str, **kwargs: Any) -> None:
        """DEBUG level log."""
        self._log("debug", event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        """INFO level log."""
        self._log("info", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        """WARNING level log."""
        self._log("warning", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """ERROR level log."""
        self._log("error", event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        """EXCEPTION level log (with exception info)."""
        self._log("exception", event, **kwargs)

    def _log(self, level: str, event: str, **kwargs: Any) -> None:
        """Internal log method."""
        # Add emoji markers
        emoji_map = {"debug": "🐛", "info": "ℹ️", "warning": "⚠️", "error": "❌", "exception": "💥"}

        # Add zoo-themed emojis
        zoo_emojis = {"worker": "🦁", "cage": "🏠", "event": "🥘", "master": "👨‍🌾", "plugin": "🔌"}

        # Merge the context
        log_data = {"event": event, "emoji": emoji_map.get(level, ""), **self._context, **kwargs}

        # Add topic emojis
        for key, emoji in zoo_emojis.items():
            if key in log_data:
                log_data[f"{key}_emoji"] = emoji

        # Emit the log
        logger_method = getattr(self._logger, level)
        if STRUCTLOG_AVAILABLE:
            logger_method(**log_data)
        else:
            # Standard-library log formatting
            extra = " ".join([f"{k}={v}" for k, v in log_data.items() if k != "event"])
            logger_method(f"{log_data.get('emoji', '')} {event} | {extra}")

    def metric(self, name: str, value: float, unit: str = "", **tags: Any) -> None:
        """Record a metric.

        P2: observability - record performance metrics automatically.

        Args:
            name: the metric name
            value: the metric value
            unit: the unit
            **tags: the tags
        """
        self.info(
            "metric_recorded",
            metric_name=name,
            metric_value=value,
            metric_unit=unit,
            metric_tags=tags,
        )


def get_logger(name: str | None = None) -> StructuredLogUtils:
    """Get a structured logger.

    Args:
        name: the logger name

    Returns:
        A structured log utility instance
    """
    logger = StructuredLogUtils()
    if name:
        logger.bind(logger_name=name)
    return logger


# 兼容性：保留旧的 LogUtils 接口
class LogUtilsCompatibility:
    """Compatible with the legacy LogUtils interface."""

    _logger: StructuredLogUtils | None = None

    @classmethod
    def _get_logger(cls) -> StructuredLogUtils:
        if cls._logger is None:
            cls._logger = StructuredLogUtils()
        return cls._logger

    @classmethod
    def debug(cls, clazz: Any, msg: Any) -> None:
        cls._get_logger().debug(
            str(msg), class_name=clazz.__name__ if hasattr(clazz, "__name__") else str(clazz)
        )

    @classmethod
    def info(cls, clazz: Any, msg: Any) -> None:
        cls._get_logger().info(
            str(msg), class_name=clazz.__name__ if hasattr(clazz, "__name__") else str(clazz)
        )

    @classmethod
    def error(cls, clazz: Any, msg: Any) -> None:
        cls._get_logger().error(
            str(msg), class_name=clazz.__name__ if hasattr(clazz, "__name__") else str(clazz)
        )


# 导出
__all__ = [
    "LogUtilsCompatibility",
    "StructuredLogUtils",
    "get_logger",
]
