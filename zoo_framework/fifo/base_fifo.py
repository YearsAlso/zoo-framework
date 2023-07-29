class BaseFIFO(object):
    _fifo = []

    def __init__(self):
        pass

    @classmethod
    def push_value(cls, value):
        cls._fifo.append(value)

    @classmethod
    def pop_value(cls):
        if len(cls._fifo) <= 0:
            return None

        return cls._fifo.pop(0)

    @classmethod
    def push_values(cls, values):
        cls._fifo.extend(values)

    @classmethod
    def size(cls):
        return len(cls._fifo)

    @classmethod
    def push_values_if_null(cls, value):
        if cls._fifo.index(value) == -1:
            cls._fifo.append(value)
