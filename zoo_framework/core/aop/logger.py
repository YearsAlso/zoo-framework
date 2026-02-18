"""
logger - zoo_framework/core/aop/logger.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

import logging

from zoo_framework.utils import LogUtils

log_utils = LogUtils()


def logger(cls):
    from zoo_framework.conf.log_config import log_config_instance

    # 创建类的日志记录器
    _logger = logging.getLogger(cls.__name__)

    _logger = log_config_instance(_logger)

    # 将日志记录器赋值给类的 _logger 属性
    cls._logger = _logger

    # 定义装饰器函数，用于添加日志记录功能
    def decorator(func):
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
