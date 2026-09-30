from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class LogParams:
    LOG_BASE_PATH = param(value="log:path", default="./logs")
    LOG_BASIC_FORMAT = "\033[37m%(asctime)s \033[36m[%(levelname)s]: \033[32;1m%(message)s\033[0m"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_LEVEL = param(value="log:level", default="info")
