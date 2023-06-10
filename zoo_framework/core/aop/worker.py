# TODO: 使用 register 的方式来注册 worker


worker_register = {}


def worker(count: int = 1):
    def inner(cls):
        """
        注册worker
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
