from zoo_framework.reactor.event_reactor_req import EventReactorReq
from zoo_framework.utils import LogUtils
from zoo_framework.event.event_channel_manager import EventChannelManager

from zoo_framework.event import EventChannel
from zoo_framework.core.aop import event
import unittest


@event("test_event", channel="test_channel")
@event("test_event2", channel="test_channel2")
def test_event(recv: EventReactorReq):
    print(recv.content)


class TestEvent(unittest.TestCase):
    def test_event_reactor(self):
        channel: EventChannel = EventChannelManager().get_channel("test_channel")
        reactors = channel.get_reactor("test_event")
        # 不通过事件通道, 直接通过事件反应器来触发事件
        for reactor in reactors:
            reactor.execute("test_event", "it‘s a test event")
            reactor.execute("test_event2", "it‘s a test event2")

    def test_event_channel(self):
        channel: EventChannel = EventChannelManager().perform("test_channel", "test_event", "it‘s a test event")
        channel: EventChannel = EventChannelManager().perform("test_channel2", "test_event2", "it‘s a test event2")
