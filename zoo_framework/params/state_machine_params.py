from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class StateMachineParams:
    PICKLE_PATH = param(value="stateMachine:picklePath", default="./zooStates.pic")
    # 状态机持久化节拍（秒，变更 configurable-run-delay / #73）：首次读盘后每隔
    # 该间隔落盘一次。默认 5 与历史硬编码一致，行为向后兼容。
    STATE_MACHINE_DELAY_TIME = param(value="stateMachine:delay", default=5)
