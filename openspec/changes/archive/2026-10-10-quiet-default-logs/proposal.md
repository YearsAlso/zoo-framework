# 提案：默认日志降噪，并让 SVM 日志不再声称未实现的能力

## Why

GitHub issue #111（B2，实测复现成立）。两个问题：

1. **默认输出是噪声**：默认级别（info）下，两个系统 Worker 每轮的 Start/Stop 各两行
   （`StateMachineWorker_1 Worker is Start/Stop`、`EventWorker_1 Worker is Start/Stop`，
   约每秒一对），外加 `🎤 Master started, zoo is open!` 等——框架自己的心跳占满屏幕，
   掩盖用户业务输出（#110 刚把业务输出变成"能被人眼看到"，本变更是它的天然续作）。
   脚手架 config.json 还把日志级别写成了 `debug`，噪声加倍。
2. **日志在撒谎（更严重）**：运行时打印 `✅ Worker 'X' registered to SVM`、
   `🔍 SVM monitoring started`、`✅ SVM Worker setup completed`——但指标链路**从未接通**：
   `record_execute()` 在框架内零调用点（grep 证实），`get_health_report()` 恒返回
   `execute_count: 0`，README 特性表如实标了 ⚠️。**日志声称监控已生效，读 API 恒为 0，
   这是"日志比文档乐观"**，直接击穿使用者对框架的信任。

## What Changes

- `base_worker.run()` 的每轮 Start/Stop 日志 `info` → `debug`（所有 Worker 生效；
  默认级别下不可见，`log.level=debug` 可重新看到——既有诊断路径保留）；
- `master.py` 的 SVM 注册/启停日志改写为**如实表述**并降为 debug，例如
  `SVM worker registered (metrics pipeline not yet wired; get_health_report() returns zeros)`——
  保留行数、删除断言性措辞（方案 b，理由见 design.md D2）；
- 脚手架 `DEFAULT_CONF` 的日志级别 `debug` → `warning`；需要诊断的人通过
  `config.json` 的 `log.level`（`debug`/`info`/`warning`/`error`/`crit`）改回；
- 排查其余"断言未实现能力"的日志/字符串：**只出清单，不顺手改**
  （初查未见第二处——未实现模式（process 等）的占位全部走显式 `NotImplementedError`
  而非乐观日志，见 design.md"实查清单"）；
- README 特性表旁已存在一行如实的 `⚠️ Metric pipeline not yet wired…`
  （`get_health_report() always reports execute_count: 0`），与日志改写后的表述一致，
  无需再改；双语 Quick Start 的"期望输出"描述按降噪后的真实观感核对一遍——
  `sample_worker` 的 `tick` 现在是默认级别下**唯一**的可见输出。

## Capabilities

- **Modified Capabilities**：
  - `worker-lifecycle`——新增 Requirement：Worker 每轮生命周期日志 MUST 为 debug 级别
    （默认不可见）；新增 Requirement：未接通的监控子系统日志 MUST NOT 声称监控已生效。
  - `project-scaffolding`——新增 Requirement：脚手架产出的 config 默认日志级别
    MUST 为 `warning`（噪声最小起点，诊断靠显式改 `log.level`）。

## Impact

- 代码：`zoo_framework/workers/base_worker.py`（2 行级别改写）、
  `zoo_framework/core/master.py`（3 处 SVM 日志改写 + 级别）、
  `zoo_framework/cli/scaffold.py`（DEFAULT_CONF 1 行）；
- 测试：新增断言"默认级别下系统 Worker 启停日志不进控制台"与"SVM 日志不含断言性
  措辞"；`test_acceptance_logs.py` 等无既有断言钉死这些日志级别（已核查）；
- 文档：无新差异（README 本就如实标注）；#110 的 README 注释
  （"框架的系统日志长得不一样"）在新默认下依然成立；
- 无第三方依赖变更；无持久化格式变更。
