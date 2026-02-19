from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

# 创建一个线程安全的字典，用于存储配置函数
config_funcs = ThreadSafeDict()


def configure(topic: str):
    """
    装饰器工厂函数，用于将函数注册到指定的主题下。

    参数:
        topic (str): 主题名称，用于标识配置函数的分类或用途。

    返回:
        function: 返回一个装饰器函数，该装饰器将传入的函数注册到 config_funcs 字典中。
    """
    def inner(func):
        # 将传入的函数以主题为键存储到线程安全字典中
        config_funcs[topic] = func
        return func

    return inner
