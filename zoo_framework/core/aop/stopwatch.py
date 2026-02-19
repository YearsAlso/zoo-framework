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
