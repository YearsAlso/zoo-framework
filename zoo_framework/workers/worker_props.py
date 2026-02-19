class WorkerProps:
    def __init__(self, name, is_loop=True, delay_time=1):
        self.is_loop = is_loop
        self.delay_time = delay_time
        self.name = name
