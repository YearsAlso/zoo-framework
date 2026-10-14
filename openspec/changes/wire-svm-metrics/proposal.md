# 提案：wire-svm-metrics —— 接通 SVM 指标链路，并给出可注册的观测接缝

## Why

README 能力表挂着一行 ⚠️：`Health monitoring (SVM) | Metric pipeline not yet wired —
get_health_report() always reports execute_count: 0`。`get_health_report()` 是公开 API，
却**恒返 0**：调用方按「健康监控可用」的前提编程，拿到的却是常量。这是内核承诺与实现
对不上的**静默降级**——正是本仓库在别处极力避免的失效模式（issue #246）。

## What Changes

- **内核只生产事实**：在唯一的结算收口处，为每次执行产出一条**不可变**的执行事实
  （Worker 身份、本次耗时、成功 / 失败），交给一个**可一次性注册 / 注销**的观察接缝。
- **SVM 作为接缝的消费者**：SVM 注册观察回调，把事实累加进自身指标，`get_health_report()`
  因此返回**真实**的 `execute_count` / `error_count` 与健康判据。
- **未注册接缝时行为不变**：没有观察者时接缝是空操作，调度与结果投递逐项不变。
- **可选 exporter**：新增 `otel` 可选附加（`pip install zoo-framework[otel]`）与**可跑示例**；
  默认依赖与「纯 Python、零依赖」不变，不装则一切如旧（与 `zoo-framework[native]` 同一先例）。
- **文档口径同步**：README（双语）该行由 ⚠️ 改 ✅；`llms.txt` / `AGENTS.md` /
  `docs/ARCHITECTURE.md` / `docs/README.md` / `docs/internal/business-plan.md` 同步；
  roadmap 的「健康监控指标链路接通」与「可观测性导出（OpenTelemetry）」两条由 Later 移入
  **Next（已立项）** 并互链 issue #246。

## Capabilities

### New Capabilities

（无——接通与接缝都挂在既有能力下，不新造能力目录。）

### Modified Capabilities

- `worker-lifecycle`：监控子系统日志的如实性判据由「未接通」改为「与接通状态一致」；
  新增「执行事实接缝」与「健康报告反映真实执行事实」两条 Requirement。
- `ci-and-packaging`：新增「观测导出面 MUST 为可选附加、不加重默认依赖、并附可跑示例」。
- `docs-consistency`：健康监控宣称的要求由「必须标注未接通」改为「必须与运行实况一致」。
- `docs-roadmap`：roadmap 与 README 的口径一致性判据更新（健康监控已接通），并要求
  已立项条目互链 issue。
- `ai-discoverability`：`llms.txt` 与 README FAQ 中「健康监控指标链路未实现」的表述更新。

## Impact

- `zoo_framework/core/execution_metrics.py`（新增，接缝）
- `zoo_framework/core/waiter/dispatch_core.py`（结算处产出执行事实）
- `zoo_framework/core/master.py`（SVM 消费接缝；日志与指标 key 口径）
- `zoo_framework/observability/`（新增，导出面）
- `pyproject.toml`（新增 `otel` 可选附加）
- `example/observability/`（新增示例）
- `README.md` / `README.zh.md` / `llms.txt` / `AGENTS.md` / `docs/ARCHITECTURE.md` /
  `docs/README.md` / `docs/internal/business-plan.md` / `docs/contributing/roadmap.md` /
  `CHANGELOG.md`
- 一致性测试：`tests/test_doc_consistency.py`、`tests/test_agent_discoverability.py`、
  `tests/test_quiet_default_logs.py`（措辞契约随实况更新，属预期连带修改）
