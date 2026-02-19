"""
stopwatch - zoo_framework/core/aop/stopwatch.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

def stopwatch(func):
    """Decorator for measuring time of function execution.
    :param func: function to be measured
    :return: function result.
    """
    from functools import wraps
    from time import time

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time()
        result = func(*args, **kwargs)
        print(f"Function {func.__name__} took {time() - start} seconds")
        return result

    return wrapper
