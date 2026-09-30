from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class StateMachineParams:
    PICKLE_PATH = param(value="stateMachine:picklePath", default="./zooStates.pic")
