class ParamsPath:
    """配置项路径。

    支持为同一配置项声明多个候选路径：按 ``value`` 优先、``aliases`` 依次回退的顺序
    解析，用于兼容历史键名。任一候选缺失时由调用方决定回退到默认值。

    Args:
        value: 首选配置路径，形如 ``worker:pool:size``
        default: 全部候选都缺失时使用的默认值
        aliases: 备选配置路径，按顺序回退
    """

    def __init__(self, value, default="", aliases=None):
        self.value = value
        self.default = default
        self.aliases = list(aliases or [])

    def get_default(self):
        return self.default

    def get_value(self):
        return self.value

    def get_aliases(self) -> list:
        return list(self.aliases)
