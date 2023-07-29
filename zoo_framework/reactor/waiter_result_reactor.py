from .base_reactor import BaseReactor
from zoo_framework.core.aop import cage


@cage
class WaiterResultHandler(BaseReactor):
    pass
