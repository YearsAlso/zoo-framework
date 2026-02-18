import pytest


def test_event_reactor():
    from zoo_framework.event import EventChannel
    event_channel = EventChannel("test_channel")
    event_channel.get_top()
    print("test_event_reactor")
