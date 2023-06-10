import logging


class LogUtils(object):
    @classmethod
    def _format_message(cls, message, cls_name):
        return "{} - {}".format(cls_name, message)

    @classmethod
    def debug(cls, message, cls_name: str = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.debug(message)

    @classmethod
    def info(cls, message, cls_name: str = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.info(message)

    @classmethod
    def warning(cls, message, cls_name: str = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.warn(message)

    @classmethod
    def error(cls, message, cls_name: str = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.error(message)
