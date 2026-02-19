"""MetaSingleton - 类功能描述

    TODO: 添加类功能详细描述
    """
meta_singleton - zoo_framework/core/meta_singleton.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

class MetaSingleton(type):
    def __init__(self, *args, **kwargs):
        self.__instance = None

    def __call__(self, *args, **kwargs):
        if not self.__instance:
            self.__instance = super().__call__(*args, **kwargs)
        return self.__instance
