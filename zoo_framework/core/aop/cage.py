"""
cage - 模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""

        if cage_register_map.get(cls.__name__) is None:
            cage_register_map[cls.__name__] = cls()
        return cage_register_map[cls.__name__]

    return _cage
"""
