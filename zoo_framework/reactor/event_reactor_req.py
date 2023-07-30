import time
import uuid


class EventReactorReq:
    """
    事件响应器请求
    """
    topic: str

    content: any

    channel: str

    reactor_name: str

    request_id: str

    request_time: float

    def __init__(self, topic: str, content: any, reactor_name: str):
        self.topic = topic
        self.content = content

        # TODO: 事件监听指定通道，防止不同通道的事件被误处理
        # self.channel = channel

        self.reactor_name = reactor_name
        self.request_id = str(uuid.uuid1())
        self.request_time = time.time()
