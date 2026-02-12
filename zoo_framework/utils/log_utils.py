import logging
from typing import Optional


class LogUtils:
    @classmethod
    def _format_message(cls, message, cls_name):
        return f"{cls_name} - {message}"

    @classmethod
    def debug(cls, message, cls_name: Optional[str] = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.debug(message)

    @classmethod
    def info(cls, message, cls_name: Optional[str] = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.info(message)

    @classmethod
    def warning(cls, message, cls_name: Optional[str] = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.warn(message)

    @classmethod
    def error(cls, message, cls_name: Optional[str] = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.error(message)
