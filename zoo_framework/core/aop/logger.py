import logging

from zoo_framework.utils import LogUtils

log_utils = LogUtils()


def logger(cls):
    """A decorator adding logging capability to a class.

    It creates a logger for the passed class and assigns it to the class's
    `_logger` attribute.

    Args:
        cls (class): the class to add logging to.

    Returns:
        class: the class with logging added.
    """
    from zoo_framework.conf.log_config import log_config_instance

    # Create the class's logger
    _logger = logging.getLogger(cls.__name__)

    _logger = log_config_instance(_logger)

    # Assign the logger to the class's `_logger` attribute
    cls._logger = _logger

    # 定义装饰器函数，用于添加日志记录功能
    def decorator(func):
        """A decorator adding logging to a function.

        Logs debug entries before and after the call, covering the function
        name and return value.

        Args:
            func (function): the function to add logging to.

        Returns:
            function: the function with logging added.
        """

        def wrapper(*args, **kwargs):
            # Log before the call
            cls._logger.debug(f"Calling {func.__name__}")

            # Run the original method
            result = func(*args, **kwargs)

            # Log after the call
            cls._logger.debug(f"{func.__name__} returned: {result}")

            return result

        return wrapper

    # Iterate over the class's methods and apply the decorator
    for name, method in cls.__dict__.items():
        if callable(method):
            setattr(cls, name, decorator(method))

    return cls
