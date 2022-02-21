class EventFIFONode(object):
    def __init__(self, value):
        self.topic = value['topic']
        self.content = value['content']
        self.handler_name = value['handler_name']
