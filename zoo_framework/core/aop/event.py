from zoo_framework.event.event_channel_register import EventChannelRegister

event_map = EventChannelRegister()


def event(topic: str, handler_name: str = "default"):
    def _event(func):
        event_map.register(handler_name, func)
        return func
    return _event
