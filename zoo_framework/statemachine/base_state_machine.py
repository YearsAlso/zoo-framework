class BaseStateMachine(dict):
    topic = ""

    def __init__(self, topic):
        dict.__init__(self)
        self.topic = topic

    def next(self, topic):
        pass
