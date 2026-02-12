class ParamsPath:
    def __init__(self, value, default=""):
        self.value = value
        self.default = default

    def get_default(self):
        return self.default

    def get_value(self):
        return self.value
