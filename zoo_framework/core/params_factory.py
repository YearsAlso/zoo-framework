import json
import os

from zoo_framework.utils import FileUtils


class ParamsFactory:
    config_params = {}

    def __init__(self, config_path="./config.json"):
        if not os.path.exists(config_path):
            return
            with open(config_path, "w") as f:
                json.dump(self.config_params, f)

        with open(config_path, "r") as f:
            ParamsFactory.config_params = json.load(f)

        # 处理 exports
        self.load_exports()

    def load_exports(self):
        export_files = self.config_params.get("_exports")
        if type(export_files) != type([]):
            return

        for export_file in export_files:
            self.load_export_file(export_file)

    def load_export_file(self, export_name):
        file_name = "./" + export_name + ".json"

        if not FileUtils.file_exists(file_name):
            return
        content = self.get_export_file(file_name)
        ParamsFactory.config_params[export_name] = content

    def get_export_file(self, file_name):
        content = {}
        try:
            with open(file_name, "r") as fp:
                content = json.load(fp)
        except:
            pass

        return content

    @classmethod
    def get_params(cls, path, default_value=""):
        if path is None or path == "":
            return default_value
        path_split = path.split(":")
        value = cls.config_params
        for item in path_split:
            if value.get(item) is None:
                return default_value
            value = value[item]
        return value
