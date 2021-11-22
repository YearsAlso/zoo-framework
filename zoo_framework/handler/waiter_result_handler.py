from .base_handler import BaseHandler
from zoo_framework.core.aop import cage


@cage
class WaiterResultHandler(BaseHandler):
    pass
