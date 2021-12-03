from multiprocessing import Process
from threading import Thread

from zoo_framework.constant import WorkerConstant
from .base_waiter import BaseWaiter


class StableWaiter(BaseWaiter):
    def __init__(self):
        BaseWaiter.__init__(self)
