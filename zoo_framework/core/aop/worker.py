"""
worker - 模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""

        if count == 1:
            worker_register.register(cls.__name__, cls())
            return cls

        for i in range(1, count + 1):
            instance = cls()
            instance.num = i
            worker_register.register(f"{cls.__name__}_{i}", instance)
        return cls

    return inner
"""
