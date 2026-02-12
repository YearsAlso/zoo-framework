from zoo_framework.reactor.event_reactor_req import EventReactorReq
from zoo_framework.utils import LogUtils
from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.fifo.node import EventNode

from zoo_framework.event import EventChannel
from zoo_framework.core.aop import event
import unittest


# 事件处理器函数（注意：不要以 test_ 开头，否则会被 pytest 识别为测试函数）
@event("test_event", channel="test_channel")
@event("test_event2", channel="test_channel2")
def handle_test_event(recv: EventReactorReq):
    print(recv.content)


class TestEvent(unittest.TestCase):
    def test_event_reactor(self):
        channel: EventChannel = EventChannelManager().get_channel("test_channel")
        reactors = channel.get_reactors("test_event")
        # 不通过事件通道, 直接通过事件反应器来触发事件
        for reactor in reactors:
            reactor.execute("test_event", "it‘s a test event")
            reactor.execute("test_event2", "it‘s a test event2")

    def test_event_channel(self):
        # 创建 EventNode 并分发事件
        event1 = EventNode(topic="test_event", content="it‘s a test event", channel_name="test_channel")
        EventChannelManager().perform_event(event1)
        
        event2 = EventNode(topic="test_event2", content="it‘s a test event2", channel_name="test_channel2")
        EventChannelManager().perform_event(event2)
