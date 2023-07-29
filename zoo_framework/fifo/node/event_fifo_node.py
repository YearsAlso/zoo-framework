class EventFIFONode(object):
    """
    事件队列节点
    """

    def __init__(self, value: dict):
        self.topic = value['topic']
        self.content = value['content']
        self.provider_name = value['provider_name']
