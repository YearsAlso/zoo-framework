import logging

from zoo_framework.utils import LogUtils

log_utils = LogUtils()


def logger(cls):
    """
    为类添加日志记录功能的装饰器。

    该装饰器会为传入的类创建一个日志记录器，并将其赋值给类的 [_logger](file:///Users/mengxiang/Projects/Persional/Architecture/zoo-framework/zoo_framework/utils/structured_log.py#L202-L202) 属性。
    同时，它会遍历类中的所有可调用方法，并为每个方法添加日志记录功能，
    在方法调用前后分别记录调试信息。

    参数:
        cls (class): 需要添加日志功能的类。

    返回:
        class: 添加了日志功能的类。
    """
    from zoo_framework.conf.log_config import log_config_instance

    # 创建类的日志记录器
    _logger = logging.getLogger(cls.__name__)

    _logger = log_config_instance(_logger)

    # 将日志记录器赋值给类的 _logger 属性
    cls._logger = _logger

    # 定义装饰器函数，用于添加日志记录功能
    def decorator(func):
        """
        为函数添加日志记录功能的装饰器。

        在函数调用前后分别记录调试日志，包括函数名和返回值。

        参数:
            func (function): 需要添加日志功能的函数。

        返回:
            function: 添加了日志功能的函数。
        """
        def wrapper(*args, **kwargs):
            # 记录方法调用前的日志
            cls._logger.debug(f"Calling {func.__name__}")

            # 执行原始方法
            result = func(*args, **kwargs)

            # 记录方法调用后的日志
            cls._logger.debug(f"{func.__name__} returned: {result}")

            return result

        return wrapper

    # 遍历类中的方法，并应用装饰器
    for name, method in cls.__dict__.items():
        if callable(method):
            setattr(cls, name, decorator(method))

    return cls
