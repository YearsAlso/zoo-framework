# project-scaffolding Specification

## Purpose

定义脚手架产出内容的正确性：生成的项目可被启动、生成的 Worker 可被导入并被调度、生成的配置可被框架读取、CLI 选项具备真实语义、产出包结构自洽、模板给出的生命周期钩子与框架实际调用的一致。该能力使开发者执行脚手架命令后得到的是一份可运行的起点，而不是一份需要通过阅读框架源码才能修好的半成品。

## Requirements

### Requirement: 脚手架产出的项目 MUST 可被启动

脚手架生成的入口文件 MUST 是可导入、可执行的合法模块，且 MUST 使用框架当前公开的构造方式。执行该入口 MUST NOT 因 API 不存在或签名不匹配而抛出异常。

#### Scenario: 生成的入口可被导入
- **WHEN** 导入脚手架生成的入口模块
- **THEN** 导入成功，不抛出 ImportError

#### Scenario: 生成的入口可被调用
- **WHEN** 调用生成入口中的启动函数
- **THEN** 框架对象被成功构造并完成 Worker 注册，不抛出 TypeError

#### Scenario: 生成的入口使用当前公开的构造方式
- **WHEN** 检查生成入口中对框架对象的构造调用
- **THEN** 其参数与该框架对象当前的公开构造签名相容

### Requirement: 脚手架产出的 Worker MUST 可被导入并被调度

脚手架生成的 Worker 模块 MUST 可被成功导入，其中的 Worker 类 MUST 可被实例化，且在被注册后 MUST 参与调度并被执行。

#### Scenario: 生成的 Worker 模块可被导入
- **WHEN** 导入脚手架生成的 Worker 模块
- **THEN** 导入成功，不抛出 ImportError

#### Scenario: 生成的 Worker 可被实例化
- **WHEN** 从生成的模块中取出 Worker 类并实例化
- **THEN** 实例化成功，不抛出异常

#### Scenario: 注册后 Worker 被调度执行
- **WHEN** 按生成入口的方式注册该 Worker 并触发调度轮次
- **THEN** 该 Worker 被执行

#### Scenario: 生成的 Worker 不依赖不存在的公开名称
- **WHEN** 检查生成模块的导入语句
- **THEN** 其中引用的每个公开名称均可从声明的模块成功导入

### Requirement: 脚手架产出的配置 MUST 被框架实际读取

脚手架生成的配置文件中的每一项设置 MUST 能被框架的配置读取路径取到，MUST NOT 因键名与读取路径不一致而被静默忽略。

#### Scenario: 产出配置中的设置可被读取
- **WHEN** 以脚手架生成的配置文件初始化框架，并经由配置读取路径查询其中声明的设置
- **THEN** 取到的值等于配置文件中声明的值，而非该设置的默认值

#### Scenario: 配置键名与读取路径一致
- **WHEN** 比对生成配置文件的键结构与框架实际查询的键路径
- **THEN** 二者一致，不存在只在配置文件中出现、而框架从不查询的键

### Requirement: CLI MUST NOT 接受不产生任何效果的选项

命令行工具暴露的每个选项 MUST 在被使用时产生可观察的效果。MUST NOT 接受一个会被静默忽略的选项；对于不受支持的选项，MUST 明确报错而非静默接受。

#### Scenario: 每个被接受的选项都产生效果
- **WHEN** 逐一使用命令行工具暴露的每个选项
- **THEN** 每个选项都产生可观察的输出差异

#### Scenario: 不受支持的选项被明确拒绝
- **WHEN** 传入一个该工具不支持的选项
- **THEN** 命令失败并指明该选项不受支持，而非静默忽略并正常退出

### Requirement: 脚手架产出的包结构 MUST 自洽

脚手架生成的项目的目录结构中，凡承担包角色的目录 MUST 具备包标识。生成的 Worker 模块 MUST 存在从入口出发可追踪的加载路径，MUST NOT 存在生成了但从不被加载的模块。

#### Scenario: 包目录均具备包标识
- **WHEN** 检查生成项目中承担包角色的每个目录
- **THEN** 每个目录都存在包标识文件

#### Scenario: 生成的 Worker 模块存在加载路径
- **WHEN** 从生成入口出发追踪模块加载
- **THEN** 生成的 Worker 模块在该路径上被加载

#### Scenario: 不存在从不被加载的生成模块
- **WHEN** 枚举项目中所有生成的模块并逐一检查其是否被入口间接导入
- **THEN** 每个生成的模块都能被追溯到

### Requirement: 模板给出的生命周期钩子 MUST 与框架实际调用的钩子一致

脚手架模板中示范的 Worker 生命周期钩子名 MUST 与框架实际调用的钩子名一致。模板 MUST NOT 给出框架从不调用的钩子。

#### Scenario: 模板钩子名与框架调用一致
- **WHEN** 取出模板中示范的全部生命周期钩子名，与框架实际调用的钩子名集合比对
- **THEN** 模板中的每个钩子名都在框架调用的集合中

#### Scenario: 模板不给出框架从不调用的钩子
- **WHEN** 检查模板中示范的钩子
- **THEN** 不存在框架在任何生产路径上都不会调用的钩子

### Requirement: 文档记录的 CLI 选项面 MUST 与实现一致

文档中给出的脚手架命令用法 MUST 只使用该命令实际支持的选项。文档 MUST NOT 示范一个不受支持的选项；当实现新增或移除选项时，文档 MUST 同步更新。

#### Scenario: 文档示例可被直接执行
- **WHEN** 逐条执行文档中给出的脚手架命令示例
- **THEN** 每条都以成功结束，不出现「不受支持的选项」类错误

#### Scenario: 文档不示范不存在的选项
- **WHEN** 取出文档中出现的全部脚手架选项名，与实际实现的选项集合比对
- **THEN** 文档中的每个选项名都在实现中存在

### Requirement: 脚手架产出的项目 MUST 开箱即含已注册且可产生可见输出的示例 Worker

`--create` 产出的入口 MUST 在 `WORKERS` 注册表中预置一个示例 Worker，使项目在
`python src/main.py` 启动后**不执行任何额外命令**即产生用户可见的业务输出。该示例
Worker MUST：

- 沿用既有 Worker 模板机制生成（类名 / 文件名符合现有 `--worker` 模板约定）；
- `_execute()` 的输出 MUST 包含 Worker 名与自增计数，使连续可见输出单调可辨（如
  `[SampleWorker] tick #1` → `#2`）；
- 注册方式与用户后续 `zfc --worker <name>` 生成的注册完全一致（同一入口标记机制）。

#### Scenario: 开箱运行即有业务输出
- **WHEN** 在临时目录执行 `--create <name>` 并直接运行产出的入口
- **THEN** 在不新增任何 Worker、不执行 `--worker` 的前提下，输出中至少含一行
  非框架日志的用户业务输出（含示例 Worker 名与计数）

#### Scenario: 示例 Worker 已被入口预注册
- **WHEN** 导入产出的入口模块并检查 `WORKERS`
- **THEN** `WORKERS` 非空，且其中的条目与入口中示例 Worker 模块的导入一一对应

#### Scenario: 示例 Worker 与后续新增 Worker 共存
- **WHEN** 在 `--create` 产出的项目中执行 `--worker my_task`
- **THEN** 入口中 demo 条目与 `MyTaskWorker` 条目并存，注册不重复、入口仍可解析

#### Scenario: 示例输出含自增计数
- **WHEN** 连续观察示例 Worker 的两次及以上输出
- **THEN** 计数单调递增，且每行输出包含 Worker 名

### Requirement: `--create` 成功时 MUST 向标准输出报告结果与下一步命令

`--create` 成功时 MUST 向标准输出生成结果摘要，至少包含：创建位置（目标目录）、
生成文件量、明确的下一句命令（`cd <name> && python src/main.py`）。失败路径契约
MUST 保持不变：非 0 退出码、报错指明原因、不产出任何文件。

#### Scenario: 成功摘要含下一步命令
- **WHEN** `--create <name>` 成功结束
- **THEN** 标准输出包含目标目录路径与"运行入口"的完整可复制命令

#### Scenario: 失败路径契约不变
- **WHEN** 目标目录已存在时执行 `--create`
- **THEN** 命令以非 0 退出码失败、指明原因，且成功摘要 MUST NOT 被打印
