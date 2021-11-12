
worker_threads = []


def worker(number: int = 1):
    def inner(cls):
        if number == 1:
            worker_threads.append(cls())
            return cls

        for i in range(1, number + 1):
            instance = cls()
            instance.num = i
            worker_threads.append(instance)
        return cls

    return inner
