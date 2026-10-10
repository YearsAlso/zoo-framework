# 提案：脚手架默认产出可运行的 demo Worker

## Why

GitHub issue #110（B1，实测复现成立）：`zfc --create myapp && cd myapp && python src/main.py`
产出的 `main.py` 中 `WORKERS = []`——一个 Worker 都没有。新用户唯一可见的输出是两个
系统 Worker（StateMachineWorker / EventWorker）的启停日志每秒刷屏，没有任何属于用户的
东西。**新用户的第一印象是"这东西什么也不干，还吵"。** 框架首启体验在 5 分钟内拿不到
正反馈，是转化漏斗的第一道关；README Quick Start（本次 `readme-first-screen` 刚重排）
也没有把 `zfc --worker` 写成获得可见输出的必要步骤。

复现记录（本仓库 Windows / Python 3.13，临时目录实测）：

- `zfc --create demoapp` → `src/main.py` 里 `WORKERS == []`（导入后逐字检查）；
- `python -u src/main.py` 的可见输出**全部**来自 LogUtils（系统 Worker Start/Stop 刷屏），
  `grep -v LogUtils` 后零行业务输出。

## What Changes

- `--create` 产出的项目**开箱即有已注册的 demo Worker**：
  - 复用现有 `worker_template` 模板机制产出一个示例 Worker 文件（不新造一套模板体系），
    `_execute()` 打印一行一眼能懂的输出（含 Worker 名与自增计数）；
  - `main_template` 的 `WORKERS` 列表**预置**该示例 Worker 的注册条目，项目开箱即跑；
- `zfc --create` 成功时向标准输出打印结果摘要：创建位置、生成文件量、明确的下一句命令
  （`cd <name> && python src/main.py`）；失败路径契约不变（非 0 退出、不留半成品）；
- 同步更新既有测试（`test_scaffold_cli_contract.py` / `test_scaffold_templates.py`），
  覆盖"默认产物含已注册 demo Worker"这一新意图；**不放宽任何既有断言**，每处
  `WORKERS == []` 之类的断言改动均标明是行为意图变更；
- 双语 README Quick Start 更新：`zfc --worker` 改为可选（demo Worker 已预置），代码块
  后贴出与实际一致的期望终端输出。

**BREAKING**：无面向既有用户的破坏——既有脚本显式执行 `zfc --worker` 的行为不变；
变化仅是"不再需要这一步才有可见输出"。

## Capabilities

- **Modified Capabilities**：`project-scaffolding`——新增两条 Requirement：
  ①脚手架产出的项目 MUST 开箱即含一个已注册且可产生可见输出的示例 Worker；
  ②`--create` 成功时 MUST 向标准输出报告结果与下一步命令。

## Impact

- 代码：`zoo_framework/templates/__init__.py`（main_template / 可能新增 demo worker 模板
  渲染）、`zoo_framework/cli/scaffold.py`（create_func 产出链 + 成功摘要打印）；
- 测试：`tests/test_scaffold_cli_contract.py`、`tests/test_scaffold_templates.py`；
- 文档：`README.md`、`README.zh.md` Quick Start 双语节（保持两半平行）；
- 无第三方依赖变更；`spec-syncer` / `docs-consistency-review` 流程照常。
