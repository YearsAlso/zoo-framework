"""state_machine_params - 状态机参数配置模块

作者: XiangMeng
版本: 0.5.2-beta
"""

from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class StateMachineParams:
    PICKLE_PATH = ParamsPath(value="stateMachine:picklePath", default="./zooStates.pic")
