import logging
import os

from zoo_framework.params import LogParams
from zoo_framework.core.aop import configure
from zoo_framework.utils import DateTimeUtils
from zoo_framework.utils import FileUtils

level_relations = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'crit': logging.CRITICAL
}


log_colors_config = {
    # 终端输出日志颜色配置
    'debug': 'white',
    'info': 'cyan',
    'warning': 'yellow',
    'error': 'red',
    'crit': 'bold_red',
}



@configure(topic="log_config")
def log_config(level: str = "info"):
    logger = logging.getLogger()
    if level_relations.get(LogParams.LOG_LEVEL) is None:
        raise Exception("Config params \"log.level\"  only support to 'debug','info','warning','error','crit'")
    
    logger.setLevel(level_relations[LogParams.LOG_LEVEL])
    
    formatter = logging.Formatter(LogParams.LOG_BASIC_FORMAT, LogParams.LOG_DATE_FORMAT)
    
    choler = logging.StreamHandler()  # 输出到控制台的handler
    choler.setFormatter(formatter)
    choler.setLevel(logging.INFO)  # 也可以不设置，不设置就默认用logger的level
    
    log_dir_path = os.path.join(LogParams.LOG_BASE_PATH, DateTimeUtils.get_format_now('%Y-%m-%d'))
    
    FileUtils.dir_exists_and_create(log_dir_path)
    
    log_path = '{}/{}.log'.format(log_dir_path, DateTimeUtils.get_format_now('%Y-%m-%d'))
    filer = logging.FileHandler(log_path)  # 输出到文件的handler
    filer.setFormatter(formatter)
    logger.addHandler(choler)
    logger.addHandler(filer)
