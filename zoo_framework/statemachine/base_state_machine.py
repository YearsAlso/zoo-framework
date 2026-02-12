class BaseStateMachine(dict):
    """Base class for all state machines."""

    topic = ""

    def __init__(self, topic):
        dict.__init__(self)
        self.topic = topic

    def next(self, topic):
        pass
