from zoo_framework import ParamPath
from zoo_framework.core.aop import params


@params
class CommonConstant:
    LOG_BASE_PATH = ParamPath(value="log:path", default="./logs")
    LOG_BASIC_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
