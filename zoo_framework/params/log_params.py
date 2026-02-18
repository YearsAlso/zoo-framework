"""
log_params - zoo_framework/params/log_params.py

模块功能描述:
TODO: 添加模块功能描述


    """LogParams - 类功能描述

    TODO: 添加类功能详细描述
    """
作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class LogParams:
    LOG_BASE_PATH = ParamsPath(value="log:path", default="./logs")
    LOG_BASIC_FORMAT = "\033[37m%(asctime)s \033[36m[%(levelname)s]: \033[32;1m%(message)s\033[0m"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_LEVEL = ParamsPath(value="log:level", default="info")
