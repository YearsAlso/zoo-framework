
config_funcs = {}


def configure(topic: str):
    def inner(func):
        config_funcs[topic] = func
        return func

    return inner