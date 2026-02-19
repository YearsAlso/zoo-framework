"""
meta_singleton - zoo_framework/core/meta_singleton.py

模块功能描述.

作者: XiangMeng
版本: 0.5.2-beta
"""

class MetaSingleton(type):
    """MetaSingleton - 类功能描述"""
    def __init__(self, *args, **kwargs):
        self.__instance = None

    def __call__(self, *args, **kwargs):
        if not self.__instance:
            self.__instance = super().__call__(*args, **kwargs)
        return self.__instance

