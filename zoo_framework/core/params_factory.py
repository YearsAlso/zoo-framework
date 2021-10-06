import json
import os


class ParamsFactory:
    config_params = {}

    def __init__(self, config_path="./config.json"):
        if not os.path.exists(config_path):
            return
            with open(config_path, "w") as f:
                json.dump(self.config_params, f)

        with open(config_path, "r") as f:
            ParamsFactory.config_params = json.load(f)

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
