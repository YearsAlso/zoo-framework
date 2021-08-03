from core import Config

from core.container.factory import ApplicationContainerFactory


def application(name):
    def wrapper(cls):
        Config.main_config()
        ApplicationContainerFactory.add_container(cls, name)
        return cls

    return wrapper
