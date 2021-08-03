import json
import logging
from core.container.factory import ConfigContainerFactory

class MasterApplication(object):
    @staticmethod
    def run(app: str, *args):
        # 加载配置
        try:
            master_config = json.load("./config.json")

        # 获得config

            ConfigContainerFactory.add_container()
        # 获得所有的worker

        # 获得所有的container

        # 通过 fork 运行 worker

        except Exception as e:
            print(str(e))
            return
