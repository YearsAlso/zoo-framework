from functools import wraps

from core.container.factory import ConfigContainerFactory


def configuration(name=""):
    def import_mod(cls):
        ConfigContainerFactory.add_container(cls, name)
        return cls

    return import_mod
