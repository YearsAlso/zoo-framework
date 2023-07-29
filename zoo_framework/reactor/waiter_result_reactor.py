from .event_reactor import EventReactor
from zoo_framework.core.aop import cage


@cage
class WaiterResultReactor(EventReactor):
    pass
