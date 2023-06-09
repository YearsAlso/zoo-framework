
worker_register = []


def worker(count: int = 1):
    def inner(cls):
        if count == 1:
            worker_register.append(cls())
            return cls

        for i in range(1, count + 1):
            instance = cls()
            instance.num = i
            worker_register.append(instance)
        return cls

    return inner
