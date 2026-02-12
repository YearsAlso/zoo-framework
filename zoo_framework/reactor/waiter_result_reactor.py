from .event_reactor import EventReactor
from zoo_framework.core.aop import cage


@cage
class WaiterResultReactor(EventReactor):

    def __init__(self):
        super().__init__("WaiterResultReactor")
        self._event_timeout = 0
