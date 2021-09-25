from core import ParamsFactory, ParamPath
from core.aop import params, singleton


@params
class CommonConstant:
    LOG_BASE_PATH = ParamPath("log:path")
    LOG_BASIC_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
