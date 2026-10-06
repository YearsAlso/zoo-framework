from .configure import config_funcs, configure
from .event import event
from .logger import logger
from .params import params
from .stopwatch import stopwatch

# 判废（变更 cleanup-aop-public-surface / issue #49）：`worker` / `worker_register` /
# `validation` 不再从本面包导出。前两者的模块路径保留一个 minor 周期并在使用时发
# DeprecationWarning；validation 模块已整删。接通路径只有一条：`Master.register_worker`。
__all__ = [
    "config_funcs",
    "configure",
    "event",
    "logger",
    "params",
    "stopwatch",
]
