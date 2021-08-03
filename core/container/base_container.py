class BaseContainer(object):

    @classmethod
    def parse_instance_params(cls, cls_name, *args, **kwargs):
        return cls_name(*args, **kwargs)

    def __init__(self, cls_name, *args, **kwargs):
        self.instance = self.parse_instance_params(cls_name, *args, **kwargs)
        self.cls_name = cls_name

    def get_instance(self):
        if self.instance is None:
            pass
        return self.instance

    def remove_instance(self):
        self.container = None

    def reload_instance(self, cls, *args, **kwargs):
        self.instance = self.parse_instance_params(cls, *args, **kwargs)
