"""cage - zoo_framework/core/aop/cage.py

模块功能描述：

作者: XiangMeng
版本: 0.5.1-beta

from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

# 单例对象注册器
cage_register_map = ThreadSafeDict()


def cage(cls):
    def _cage():
        """用于单例模式的装饰器."""
        if cage_register_map.get(cls.__name__) is None:
            cage_register_map[cls.__name__] = cls()
        return cage_register_map[cls.__name__]

    return _cage
