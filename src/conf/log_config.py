import logging
import os

from constant.common_constant import CommonConstant
from core.aop import configure
from utils import DateTimeUtils
from utils import FileUtils

level_relations = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'crit': logging.CRITICAL
}


@configure(topic="log_config")
def log_config(level: str = "info"):
    logger = logging.getLogger()
    logger.setLevel(level_relations[level])

    formatter = logging.Formatter(CommonConstant.LOG_BASIC_FORMAT, CommonConstant.LOG_DATE_FORMAT)

    chlr = logging.StreamHandler()  # 输出到控制台的handler
    chlr.setFormatter(formatter)
    chlr.setLevel(logging.INFO)  # 也可以不设置，不设置就默认用logger的level

    log_dir_path = os.path.join(CommonConstant.LOG_BASE_PATH, DateTimeUtils.get_format_now('%Y-%m-%d'))

    FileUtils.dir_exists_and_create(log_dir_path)

    log_path = '{}/{}.log'.format(log_dir_path, DateTimeUtils.get_format_now('%Y-%m-%d'))
    fhlr = logging.FileHandler(log_path)  # 输出到文件的handler
    fhlr.setFormatter(formatter)
    logger.addHandler(chlr)
    logger.addHandler(fhlr)
