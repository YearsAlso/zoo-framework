"""configure - zoo_framework/core/aop/configure.py

模块功能描述：

作者: XiangMeng
版本: 0.5.1-beta

from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

config_funcs = ThreadSafeDict()


def configure(topic: str):
    def inner(func):
        config_funcs[topic] = func
        return func

    return inner
