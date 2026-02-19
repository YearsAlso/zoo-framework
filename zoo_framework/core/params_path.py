"""
params_path - 模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""


    def __init__(self, value, default=""):
        self.value = value
        self.default = default

    def get_default(self):
        return self.default

    def get_value(self):
        return self.value

    def __str__(self):
        return f"ParamsPath(value={self.value}, default={self.default})"
"""
