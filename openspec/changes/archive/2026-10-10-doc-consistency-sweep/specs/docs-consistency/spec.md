# docs-consistency Spec Delta — doc-consistency-sweep

## ADDED Requirements

### Requirement: 面向读者的文档 MUST NOT 陈述与运行实况可测不符的事实

文档中影响使用者决策的可机械核对陈述（版本号、Python 门槛、测试规模、能力
接通状态）SHALL 与仓库实况一致。一致性测试 SHALL 从仓库真源（`pyproject.toml`
的 `version` / `requires-python`、全量 pytest collect 结果）取得实况，文档中的
对应陈述 MUST 与之相符。

#### Scenario: Python 门槛陈述与 pyproject 一致
- **WHEN** 文档中出现 Python 版本门槛陈述
- **THEN** 它与 `pyproject.toml` 的 `requires-python` 一致（当前 3.13），
  陈旧版本号（如 3.8）MUST NOT 出现在贡献者文档的环境要求里

#### Scenario: 测试规模不得硬编码会漂移的数字
- **WHEN** 一批测试合入或删除使全量用例数改变
- **THEN** 文档一致性测试不因文档里的具体数字而失败——面向读者的文档引用
  Tests 徽章而非硬编码用例数；维护者速览文档（structure.md）中的数字 SHALL
  由快照维持并与实况可核对（故意改坏一处数字时测试 MUST 变红）

#### Scenario: 版本号一致性
- **WHEN** 文档中出现具体版本号陈述
- **THEN** 该陈述与 `pyproject.toml` 的 `version` 不冲突（文档优先用徽章/动态
  来源而非硬编码）

### Requirement: 健康监控的宣称 MUST 如实标注指标链路状态

`get_health_report()` 指标输入链路尚未接通（恒返回 `execute_count: 0`）这一事实
SHALL 在每一处宣称"SVM 健康监控"能力的地方可见：文档中不得出现无标注的
"自动故障检测""监控已在生效"级宣称；运行时日志 MUST NOT 输出已废弃的
`SVM monitoring started` 字样（B2 已将其诚实化）。

#### Scenario: 能力宣称处可见未接通标注
- **WHEN** 文档某处把"SVM 健康监控"列为关键特性或优势
- **THEN** 该处带"指标链路尚未接通 / `get_health_report()` 恒为 0"级别的标注

#### Scenario: 废弃宣称词不得回归
- **WHEN** 全库文档与运行时日志源码被扫描
- **THEN** `SVM monitoring started` 这类已废弃的不实宣称字样出现次数为 0

### Requirement: 不可核实的生产背书 MUST NOT 出现在对外文档

依赖私有项目（读者无从核实）的生产验证宣称 SHALL 改写为不依赖项目身份、
可被仓库内证据支撑的表述；私有项目名 MUST NOT 作为对外信任背书出现。

#### Scenario: ELS 背书被替换
- **WHEN** 读者阅读路线图或商业计划中的"生产就绪"一节
- **THEN** 看到的是可核实的表述，私有项目名不出现在对外有效的文档中

### Requirement: 隐喻映射表 SHALL 三处同源

README.md（英文）、README.zh.md（中文）、CLAUDE.md 三份文件的隐喻映射表
SHALL 描述同一组映射（Worker→任务执行单元、Master→Master、Waiter→调度器、
Cage→ScopedContainer、Event→事件、FIFO→EventFIFO、Reactor→EventReactor、
StateMachine→StateMachineManager）；一致性测试 SHALL 解析三份表格并断言
映射一致。历史隐喻名（Zookeeper / Food / Feeder queue）MUST NOT 作为组件
映射出现——它们在代码中零引用。

#### Scenario: 三处映射一致
- **WHEN** 解析三份文件的隐喻表
- **THEN** 表中「隐喻 → 组件」映射集合一致（允许语言差异，不允许映射对象不同）

#### Scenario: 废弃映射不得回归
- **WHEN** 任何文档把 Zookeeper 映射到 Master、或 Food/Feeder 映射到 Event/FIFO
- **THEN** 一致性测试失败（这些名字在代码里零匹配，映射以代码实况为准）
