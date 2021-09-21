from core import ParamsFactory
from core.aop import params


class CommonConstant:
    LOG_BASE_PATH = ParamsFactory.config_params("log:path", "./log")
    LOG_BASIC_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
