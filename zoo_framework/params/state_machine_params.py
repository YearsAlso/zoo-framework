from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class StateMachineParams:
    PICKLE_PATH = param(value="stateMachine:picklePath", default="./zooStates.pic")
    # 状态机持久化节拍（秒，变更 configurable-run-delay / #73）：首次读盘后每隔
    # 该间隔落盘一次。默认 5 与历史硬编码一致，行为向后兼容。
    STATE_MACHINE_DELAY_TIME = param(value="stateMachine:delay", default=5)
    # 查询型索引类型（add-state-query-index-and-incremental-persistence 原语 2）：
    # 选择 `StateIndexFactory` 中注册的索引实现名，默认 "dict" 即现状默认索引。
    # 该键在 scope 构造期（运行期）读取，避免 `@params` 在首次导入时冻结默认值。
    STATE_INDEX_TYPE = param(value="stateMachine:indexType", default="dict")
    # 增量持久化开关（原语 3）：开启后 `picklePath` 解释为目录，每拍只写脏作用域
    # 的文件。默认 False = 现状整表落盘，行为向后兼容。运行期读取。
    INCREMENTAL_SAVE = param(value="stateMachine:incrementalSave", default=False)
    # 作用域 TTL（秒，原语 3）：按 `StateScope.last_modified`（墙钟、最后写入）
    # 淘汰过期作用域。0 表示不淘汰（现状默认）。运行期读取。
    SCOPE_TTL_SECONDS = param(value="stateMachine:scopeTtlSeconds", default=0)
