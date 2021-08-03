from core.container.factory import WorkerContainerFactory


def worker(*args, **kwargs):
    def wrapper(cls):
        # TODO 指定类
        if not isinstance(cls, object):
            raise Exception("")
            return

        WorkerContainerFactory.add_container(cls, "")
        return cls

    return wrapper
