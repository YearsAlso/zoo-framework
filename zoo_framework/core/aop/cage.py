cage_list = []


def cage(cls):
    def _cage():
        if cls not in cage_list:
            cage_list[cls] = cls()
        return cage_list[cls]

    return _cage

