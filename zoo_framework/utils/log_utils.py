"""
log_utils - zoo_framework/utils/log_utils.py

模块功能描述：
    """LogUtils - 类功能描述

    TODO: 添加类功能详细描述
    """
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

import logging


class LogUtils:
    @classmethod
    def _format_message(cls, message: str, cls_name: str) -> str:
        return f"{cls_name} - {message}"

    @classmethod
    def debug(cls, message: str, cls_name: str | None = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.debug(message)

    @classmethod
    def info(cls, message: str, cls_name: str | None = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.info(message)

    @classmethod
    def warning(cls, message: str, cls_name: str | None = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.warning(message)

    @classmethod
    def error(cls, message: str, cls_name: str | None = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.error(message)
