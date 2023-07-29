from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class EventParams:
    EVENT_JOIN_TIMEOUT = ParamsPath(value="event:timeout", default=5)
    EVENT_SLEEP_TIME = ParamsPath(value="event:sleep", default=0.2)
