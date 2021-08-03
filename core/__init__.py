from core.configer.base_configer import BaseConfiger
from core.configer import *
from core.params import *
from core.container import configers


class Config(object):
    @staticmethod
    def main_config():
        Config().configure_init()

    @staticmethod
    def configure_init():
        for k in configers.keys():
            configer = configers[k]
            if isinstance(configer, BaseConfiger):
                configer.config()

    @staticmethod
    def configure_prop():
        pass
