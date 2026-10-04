from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class EventParams:
    EVENT_JOIN_TIMEOUT = param(value="event:timeout", default=5)
    EVENT_SLEEP_TIME = param(value="event:sleep", default=0.2)
