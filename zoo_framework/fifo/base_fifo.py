class BaseFIFO(object):
    fifo = []
    
    def __init__(self):
        pass

    @classmethod
    def push_value(cls, value):
        cls.fifo.append(value)

    @classmethod
    def pop_value(cls):
        if len(cls.fifo) <= 0:
            return None

        return cls.fifo.pop(0)

    @classmethod
    def push_values(cls, values):
        cls.fifo.extend(values)

    @classmethod
    def size(cls):
        return len(cls.fifo)

    @classmethod
    def push_values_if_null(cls, value):
        if cls.fifo.index(value) == -1:
            cls.fifo.append(value)
