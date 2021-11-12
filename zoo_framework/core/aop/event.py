

event_map = {}


def event(topic: str):
    def inner(func):
        event_map[topic] = func
        return func

    return inner