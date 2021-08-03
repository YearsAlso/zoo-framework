from core.container import params


class BaseParams(object):
    def __init__(self):
        pass

    @classmethod
    def load_properties(cls, file_path: str = "properties.yml"):
        pass

    @classmethod
    def set_params(cls, *args, **kwargs):
        pass

    @classmethod
    def get_params(cls, key):
        cls_params = params.get(cls.__name__)
        if cls_params is None:
            return None
        return cls_params.get(key)

    @classmethod
    def get_all_params(cls):
        return params.get(cls.__name__)
