
from zoo_framework.utils import LogUtils


def logger(cls):
    def _logger():
        """
        用于单例模式的装饰器
        """
        inst = cls()
        setattr(inst, "logger", LogUtils)
        return inst

    return _logger
