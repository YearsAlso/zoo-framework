import logging
from datetime import datetime

from core.aop.configuration import configuration
from core.configer.base_configer import BaseConfiger


@configuration(name="LogConfiger")
class LogConfiger(BaseConfiger):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    @configuration
    def config(*args, **kwargs):
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
