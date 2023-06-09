from zoo_framework.core.thread_safe_dict import ThreadSafeDict

config_funcs = ThreadSafeDict()


def configure(topic: str):
    def inner(func):
        config_funcs[topic] = func
        return func

    return inner
