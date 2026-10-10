# 提案：zfc --worker 生成的类名转 PascalCase

## Why

GitHub issue #112（B3，实测复现成立）：`zfc --worker my_task` 生成的类名是
`My_TaskWorker` —— `str.title()` 只把每个下划线后首字母大写，**下划线本身保留**，
不产 PascalCase。脚手架产物承载使用者的整个项目，三处标识符（文件名、类名、
入口 `WORKERS` 注册元组的注册名）目前没有统一规则：现状是类名 `My_TaskWorker`
**同时充当注册名**（`master.register_worker(name, worker_class)` 的 name 直接取
WORKERS 元组首项 = 类名字符串）。

## What Changes

- `_worker_names` 的类名推导从 `worker_name.title() + "Worker"` 改为
  snake_case → PascalCase + `"Worker"`：`order_sync` → `OrderSyncWorker`、
  `my_task` → `MyTaskWorker`（规则与边界见 design.md D-Rules）；
- 三处一致性随之自然成立：文件名 `my_task_worker.py`、类名/注册名
  `MyTaskWorker`（注册名仍等于类名字符串，现状已如此，本变更使它**有规则可循**）；
- 输入校验零回归：非法标识符拒绝行为、非 0 退出、不留半成品的既有断言全部保留；
- 既有测试更新：`My_TaskWorker` 断言组合（5 处）翻转到 `MyTaskWorker`，属行为
  意图变更，docstring 标注；
- 模板预置示例（`sample` → `SampleWorker`）在新规则下**不变**——#110 的产物与
  `[sample_worker] tick` 输出形态零改动。

**BREAKING**：无 —— 旧名 `My_TaskWorker` 只存在于"刚生成还未被引用"的产物里；
已写入用户项目的文件不会被本变更改名或破坏（也不该：框架不回收用户文件）。
仅新生成的产物获得新命名。

## Capabilities

- **Modified Capabilities**：`cli-scaffolding` —— MODIFIED 既有 Requirement
  「新增 Worker 的名称 MUST 是合法标识符」（合法名产出物新增命名规则条款：
  类名 = PascalCase(输入) + "Worker"，三处一致），并新增边界情况 Scenario
  （连续下划线、前后置下划线、单字母、`v2e` 型数字混排、已带 `worker` 后缀）。

## Impact

- 代码：`zoo_framework/cli/scaffold.py` 的 `_worker_names`（1 处函数体）；
- 测试：`tests/test_scaffold_templates.py`（5 处 `My_TaskWorker` 引用）、
  `tests/test_scaffold_cli_contract.py`（类名推导用例与拒绝行为用例并行保留）；
- 文档：README 双语 Quick Start 示例中 `my_task` 产出类名提示（若有具体类名
  字样则同步；本变更前 README 未出现 `My_TaskWorker` 字样，实测 grep 为零，
  预计零改动）；
- 不触及 `worker_registry`、`@worker` 装饰器、持久化格式；无第三方依赖变更。
