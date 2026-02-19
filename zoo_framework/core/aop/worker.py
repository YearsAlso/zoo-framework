# TODO: 使用 register 的方式来注册 worker
from zoo_framework.workers import WorkerRegister

worker_register: WorkerRegister = WorkerRegister()


def worker(count: int = 1):
    """装饰器函数，用于注册指定数量的 worker 实例。

    参数:
        count (int): 需要注册的 worker 实例数量，默认为 1。

    返回:
        function: 返回一个内部装饰器函数，用于处理被装饰的类。
    """

    def inner(cls):
        """内部装饰器函数，负责实际的 worker 注册逻辑。

        参数:
            cls (class): 被装饰的类，表示 worker 的类型。

        返回:
            class: 返回原始类，保持装饰器的透明性。
        """
        # 如果只需要注册一个实例，则直接注册该类的实例
        if count == 1:
            worker_register.register(cls.__name__, cls())
            return cls

        # 如果需要注册多个实例，则为每个实例分配编号并分别注册
        for i in range(1, count + 1):
            instance = cls()
            instance.num = i
            worker_register.register(f"{cls.__name__}_{i}", instance)
        return cls

    return inner
