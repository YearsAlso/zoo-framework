"""log_params - 日志参数配置模块

作者: XiangMeng
版本: 0.5.2-beta
"""

from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class LogParams:
    LOG_BASE_PATH = ParamsPath(value="log:path", default="./logs")
    LOG_BASIC_FORMAT = "\033[37m%(asctime)s \033[36m[%(levelname)s]: \033[32;1m%(message)s\033[0m"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_LEVEL = ParamsPath(value="log:level", default="info")
