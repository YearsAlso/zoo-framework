cage_list = {}


def cage(cls):
    def _cage():
        if cls not in cage_list:
            cage_list[cls.__name__] = cls()
        return cage_list[cls.__name__]

    return _cage

