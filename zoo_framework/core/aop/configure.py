from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

# 创建一个线程安全的字典，用于存储配置函数
#
# 【已知欠债】模块级注册表、进程级共享；须由测试单独复位（见
# tests/test_scaffold_cli_contract.py 的清理辅助）。属容器外、未收编的载体；依据与判据见
# specs/scoped-container 的「框架自身的进程级共享 MUST 被显式归类」。
config_funcs = ThreadSafeDict()


def configure(topic: str):
    """装饰器工厂函数，用于将函数注册到指定的主题下。

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
