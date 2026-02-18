
版本: 0.5.1-beta

from zoo_framework.core.aop import cage

from .event_reactor import EventReactor


@cage
class WaiterResultReactor(EventReactor):
    def __init__(self):
        super().__init__("WaiterResultReactor")
        self._event_timeout = 0
