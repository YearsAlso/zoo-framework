"""
configure.py - AOP模块

提供面向切面编程功能。

作者: XiangMeng
版本: 0.5.2-beta
"""

# 占位符实现 - 实际功能需要根据原始代码恢复

# 全局配置函数注册表：Master 在启动时会调用其中的函数
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

config_funcs = ThreadSafeDict()


def configure(topic: str):
    def inner(func):
        config_funcs[topic] = func
        return func

    return inner

