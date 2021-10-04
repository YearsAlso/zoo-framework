class ParamPath(str):

    def __init__(self, value, default=""):
        str.__init__(value)
        self.default = default

    def get_default(self):
        return self.default
