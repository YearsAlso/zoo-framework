"""log_utils - zoo_framework/utils/log_utils.py

日志工具模块,提供日志记录功能.

功能:
- 日志配置管理
- 多级别日志记录
- 结构化日志输出
- 日志文件轮转

作者: XiangMeng
版本: 0.5.1-beta
"""

import logging
import sys


class LogUtils:
    """日志工具类

    提供日志记录相关的实用方法.
    """

    @classmethod
    def get_logger(cls, name: str, level: int = logging.INFO) -> logging.Logger:
        """获取配置好的日志记录器"""
        logger = logging.getLogger(name)
        logger.setLevel(level)

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    @classmethod
    def setup_file_logging(
            cls,
            logger: logging.Logger,
            filepath: str,
            level: int = logging.INFO
    ) -> None:
        """设置文件日志记录"""
        file_handler = logging.FileHandler(filepath)
        file_handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    @classmethod
    def log_debug(cls, logger: logging.Logger, message: str, **kwargs) -> None:
        """记录调试日志"""
        logger.debug(message, extra=kwargs)

    @classmethod
    def log_info(cls, logger: logging.Logger, message: str, **kwargs) -> None:
        """记录信息日志"""
        logger.info(message, extra=kwargs)

    @classmethod
    def log_warning(cls, logger: logging.Logger, message: str, **kwargs) -> None:
        """记录警告日志"""
        logger.warning(message, extra=kwargs)

    @classmethod
    def log_error(cls, logger: logging.Logger, message: str, **kwargs) -> None:
        """记录错误日志"""
        logger.error(message, extra=kwargs)

    @classmethod
    def log_critical(cls, logger: logging.Logger, message: str, **kwargs) -> None:
        """记录严重错误日志"""
        logger.critical(message, extra=kwargs)

    @classmethod
    def set_log_level(cls, logger: logging.Logger, level: str) -> None:
        """设置日志级别"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        logger.setLevel(level_map.get(level.upper(), logging.INFO))
