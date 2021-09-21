import json

from core import singleton


@singleton
class ParamsFactory:
    config_params = {}

    def __init__(self, config_path="./config.json"):
        with open(config_path) as f:
            self.config_params = json.load(f)

    def get_params(self, path, default_value = ""):
        if path is None or path == "":
            return default_value
        path_split = path.split(":")
        value = self.config_params
        for item in path_split:
            if value[item] is None:
                return default_value
            value = value[item]
        return value
