class BaseFIFO(object):
    fifo = []
    
    def __init__(self):
        pass
    
    def push_value(self, value):
        self.fifo.append(value)
    
    def pop_value(self):
        return self.fifo.pop(0)
    
    def push_values(self, values):
        self.fifo.extend(values)
    
    def size(self):
        return len(self.fifo)
    
    def push_values_if_null(self, value):
        if self.fifo.index(value) == -1:
            self.fifo.append(value)
