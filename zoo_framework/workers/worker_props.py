"""
worker_props - zoo_framework/workers/worker_props.py

模块功能描述.

作者: XiangMeng
版本: 0.5.2-beta
"""

class WorkerProps:
    """WorkerProps - 类功能描述"""
    def __init__(self, name, is_loop=True, delay_time=1):
        self.is_loop = is_loop
        self.delay_time = delay_time
        self.name = name

