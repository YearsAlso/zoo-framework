class BaseContainer(object):

    @classmethod
    def parse_instance_params(cls, _cls, *args, **kwargs):
        return _cls(*args, **kwargs)

    def __init__(self, cls, *args, **kwargs):
        self.instance = self.parse_instance_params(cls, *args, **kwargs)

    def get_instance(self):
        if self.instance is None:
            pass
        return self.instance

    def remove_instance(self):
        self.container = None

    def reload_instance(self, cls, *args, **kwargs):
        self.instance = self.parse_instance_params(cls, *args, **kwargs)
