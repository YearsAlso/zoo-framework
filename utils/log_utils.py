import logging
from datetime import datetime


class LogUtils(object):
    __log = None
    
    @staticmethod
    def init_logging():
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
    
        BASIC_FORMAT = "%(asctime)s [%(levelname)s]: %(name)s - %(message)s"
        DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter(BASIC_FORMAT, DATE_FORMAT)
    
        chlr = logging.StreamHandler()  # 输出到控制台的handler
        chlr.setFormatter(formatter)
        chlr.setLevel(logging.INFO)  # 也可以不设置，不设置就默认用logger的level
    
        fhlr = logging.FileHandler(
            'E:\\FTPServer\\logs\\{}-panophoto.log'.format(datetime.now().strftime("%Y-%m-%d")))  # 输出到文件的handler
        fhlr.setFormatter(formatter)
        logger.addHandler(chlr)
        logger.addHandler(fhlr)
    
    def __class__(cls):
        if cls.__log is None:
            cls.init_logging()
