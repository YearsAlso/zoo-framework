import logging
import os

from zoo_framework.core.aop import configure
from zoo_framework.params import LogParams
from zoo_framework.utils import DateTimeUtils, FileUtils, SafeStreamHandler

level_relations = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "crit": logging.CRITICAL,
}

log_colors_config = {
    # 终端输出日志颜色配置
    "debug": "white",
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "crit": "bold_red",
}


@configure(topic="log_config")
def log_config(level: str = "info"):
    logger = logging.getLogger()
    log_config_instance(logger, level)


def log_config_instance(logger, level: str = "info"):
    if level_relations.get(LogParams.LOG_LEVEL) is None:
        raise Exception(
            "Config params \"log.level\"  only support to 'debug','info','warning','error','crit'"
        )

    logger.setLevel(level_relations[LogParams.LOG_LEVEL])

    formatter = logging.Formatter(LogParams.LOG_BASIC_FORMAT, LogParams.LOG_DATE_FORMAT)

    choler = SafeStreamHandler()  # 输出到控制台的handler
    choler.setFormatter(formatter)
    # handler 不再自带级别硬门：跟随 logger 级别。原先固定 INFO 会把 log.level=debug
    # 的记录在 handler 层整段过滤，"诊断时改回 debug"路径形同虚设（#111 实测复现）

    log_dir_path = os.path.join(LogParams.LOG_BASE_PATH, DateTimeUtils.get_format_now("%Y-%m-%d"))

    FileUtils.dir_exists_and_create(log_dir_path)

    log_path = "{}/{}.log".format(log_dir_path, DateTimeUtils.get_format_now("%Y-%m-%d"))
    # 日志文件显式以 UTF-8 写出：依赖平台默认编码会让含 emoji / 中文的日志在
    # 非 UTF-8 平台上整行丢失，也会让日志文件无法被跨平台读取
    filer = logging.FileHandler(log_path, encoding=FileUtils.DEFAULT_ENCODING)
    filer.setFormatter(formatter)
    logger.addHandler(choler)
    logger.addHandler(filer)
    return logger
