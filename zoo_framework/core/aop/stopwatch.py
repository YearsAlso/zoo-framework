"""
stopwatch - 模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
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
"""
