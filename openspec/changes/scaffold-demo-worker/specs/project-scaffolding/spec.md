# project-scaffolding Spec Delta — scaffold-demo-worker

## ADDED Requirements

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
