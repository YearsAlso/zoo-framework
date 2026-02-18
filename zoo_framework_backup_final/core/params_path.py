"""params_path - zoo_framework/core/params_path.py

参数路径处理模块，用于管理和解析配置参数路径。

功能：
- 参数路径的解析和验证
- 默认值管理
- 路径格式标准化

作者: XiangMeng
版本: 0.5.1-beta


class ParamsPath:
    """参数路径类

    用于处理配置参数的路径，支持默认值和路径解析。

    属性：
        value: 参数路径值
        default: 默认值（当路径不存在时使用）

    示例：
        >>> path = ParamsPath('database.host', 'localhost')
        >>> print(path.value)
        'database.host'
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
