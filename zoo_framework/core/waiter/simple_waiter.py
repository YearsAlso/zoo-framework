"""
simple_waiter - 模块功能描述。

作者: XiangMeng
版本: 0.5.2-beta
"""


simple_waiter - zoo_framework/core/waiter/simple_waiter.py

模块功能描述:

TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

from .base_waiter import BaseWaiter


class SimpleWaiter(BaseWaiter):
    """SimpleWaiter - 类功能描述"""
    def __init__(self):
        BaseWaiter.__init__(self)

    # 集结worker们
    def call_workers(self, worker_list):
        if len(worker_list) > self.pool_size:
            self.pool_size = len(worker_list) + 1
        super().call_workers(worker_list)
"""
