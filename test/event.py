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
    def test_event(self):
        channel: EventChannel = EventChannelManager().get_channel("test_channel")
        reactor = channel.get_reactor("test_event")
        reactor.execute("test_event", "it‘s a test event")
        reactor.execute("test_event2", "it‘s a test event2")
