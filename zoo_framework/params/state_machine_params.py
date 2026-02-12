from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class StateMachineParams:
    PICKLE_PATH = ParamsPath(value="stateMachine:picklePath", default="./zooStates.pic")
