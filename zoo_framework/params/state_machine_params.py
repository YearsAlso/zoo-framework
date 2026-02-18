"""
state_machine_params - zoo_framework/params/state_machine_params.py

模块功能描述：
TODO: 添加模块功能描述


    """StateMachineParams - 类功能描述

    TODO: 添加类功能详细描述
    """
作者: XiangMeng
版本: 0.5.1-beta
"""

from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class StateMachineParams:
    PICKLE_PATH = ParamsPath(value="stateMachine:picklePath", default="./zooStates.pic")
