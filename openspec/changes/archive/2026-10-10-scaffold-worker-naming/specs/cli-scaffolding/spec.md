# cli-scaffolding Spec Delta — scaffold-worker-naming

## MODIFIED Requirements

### Requirement: 新增 Worker 的名称 MUST 是合法标识符

命令行工具在接受一个 Worker 名称时 MUST 先校验该名称可作为 Python 标识符使用：
不以数字开头、不含连字符与空白、不是 Python 关键字。校验不通过时命令 MUST 以非 0
退出码失败并指明原因，MUST NOT 产出任何文件。

合法名称的产物标识符 SHALL 遵循统一规则：**类名 = PascalCase(输入名) + "Worker"**，
其中 PascalCase 按下划线分段、每段首字母大写后拼接（下划线不保留）。文件名、类名、
入口注册名三者 SHALL 一致：文件名为 `<输入名>_worker.py`，注册名等于类名字符串。

#### Scenario: 非法名称被拒绝
- **WHEN** 以一个含连字符的名称请求新增 Worker
- **THEN** 命令以非 0 退出码失败，且输出指明该名称非法

#### Scenario: 非法名称不产出任何文件
- **WHEN** 以一个以数字开头的名称请求新增 Worker
- **THEN** 工作目录下不产生新增的模块文件，且既有文件内容不变

#### Scenario: 合法名称被接受
- **WHEN** 以一个合法标识符名称请求新增 Worker
- **THEN** 命令成功，产出的模块与入口均可被解析

## ADDED Requirements

### Requirement: 脚手架示例 Worker 的预置注册 MUST 与命名规则自洽

#### Scenario: 蛇形名转 PascalCase 类名
- **WHEN** 以 `order_sync` 请求新增 Worker
- **THEN** 产出类名为 `OrderSyncWorker`，注册名与其一致

#### Scenario: 下划线在类名中不保留
- **WHEN** 以 `my_task` 请求新增 Worker
- **THEN** 产出类名为 `MyTaskWorker`（而非 `My_TaskWorker`）

#### Scenario: 连续下划线与前导下划线
- **WHEN** 以 `x__y` 或 `_private` 请求新增 Worker
- **THEN** 产出类名分别为 `XYWorker` 与 `PrivateWorker`（空段被跳过，不产生
  空段首字母）

#### Scenario: 数字混排段
- **WHEN** 以 `v2e` 请求新增 Worker
- **THEN** 产出类名为 `V2eWorker`（段内仅首字母大写，其余字符不变）

#### Scenario: 输入已含 worker 后缀
- **WHEN** 以 `sample` 及 `sample_worker` 分别请求新增 Worker
- **THEN** 前者产出 `SampleWorker`；后者产出 `SampleWorkerWorker`
  （输入被原样视为名称主体，后缀剥离不做——名字是使用者语义的一部分，
  工具不代为裁剪）

## ADDED Requirements

### Requirement: 脚手架示例 Worker 的预置注册 MUST 与命名规则自洽

`--create` 预置的示例 Worker（`sample`）SHALL 产自同一命名规则（类名
`SampleWorker`），且 SHALL 与用户后续 `--worker` 新增的 Worker 在命名上
同源——不存在两套推导逻辑。

#### Scenario: 示例与用户新增同规则
- **WHEN** 对比 `--create` 预置条目与 `--worker sample` 产出的类名
- **THEN** 二者同为 `SampleWorker`，入口只登记一处（幂等接线判重不二次追加）
