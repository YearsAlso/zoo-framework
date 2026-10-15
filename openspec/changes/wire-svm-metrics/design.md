## Context

见 proposal.md 的 Why。当前状态：`SVMWorker`（`zoo_framework/core/master.py`）持有每 Worker 的
`_metrics`，但**没有任何路径调用 `record_execute`**——执行事实不存在。派发路径的**唯一结算收口**
是 `WorkerDispatchCore.settle`（`core/waiter/dispatch_core.py`）：两种调度模型（thread / thread_pool）
都经 `run_and_settle → settle` 收口。`worker-lifecycle` 已有「监控日志不得虚假宣称」的 Requirement，
`docs-consistency` / `docs-roadmap` / `ai-discoverability` 各自把「未接通」写进了对外口径。

## Goals / Non-Goals

**Goals:**

- 让 `get_health_report()` 的 `execute_count` / `error_count` 由**真实执行事实**累加而来。
- 提供一个**内核只生产事实、不决定去哪**的可注册观察接缝，形态与既有 `observe_state` /
  `StateEffect` 扩展点同构。
- 未注册接缝时行为逐项不变；注销后无泄漏。
- 观测导出作为**可选附加 + 可跑示例**，不加重默认依赖。

**Non-Goals:**

- 不冻结一份完整的指标清单（清单随后由消费方驱动）。
- 不改健康判据的**阈值语义**（`_check_workers_health` 的 0.2 / 0.5 与 `> 10` 门槛一字不改）。
- 不新增默认依赖；不改调度模型与事件管道。
- 不承诺「自动终止 / 自动修复」——超期仍只观测与熔断。

## Decisions

### D1：接缝形态 —— 与 `observe_state` / `StateEffect` 同构的注册式观察

新增 `zoo_framework/core/execution_metrics.py`：

- `ExecutionFact`：`frozen dataclass`（`worker_name` / `duration` / `success`）。**不可变**是硬性
  要求——可变对象经引用传递给多个消费者会被就地改写，断言与消费都会读到最终态（`.claude/rules/
  assertion-integrity.md`）。
- `ExecutionObserverRegistry`：以 `@process_scoped` 装饰的进程级注册表，暴露
  `observe(callback)` / `unobserve(callback)` / `observers()` / `emit(fact)`，内部为实例态
  `list` + `RLock`。它与 `StateMachineManager.observe_state` 同构：注册回调、内部持有、触发时遍历调用。
- 内核侧只在 `settle` 里调用 `ExecutionObserverRegistry().emit(fact)`，**不 import 任何消费者**。

**为何不用模块级 list**：`tests/test_process_state_registry.py` 会扫描框架全部模块级 / 类级可变容器，
未在 `core/process_state.py:CARRIERS` 归类即红。用 `@process_scoped` 的**实例态**则自动归入容器复位
（`framework_container().reset()` 已在册），无需新增归类项，且与 `EventReactorManager` 等既有共享同形。

**替代方案**：（a）模块级 list + 新增 CARRIERS 条目——可行但多一处显式归类，且与容器化方向相悖；
（b）把观察表挂在每个 `WorkerDispatchCore` 上——消费者需按调度器注册，导出方无法「一次注册」全局生效，
否决。

### D2：事实产出点 —— 唯一的结算收口 `settle`

`settle` 已持有登记项（含 `run_time` 单调起点），是唯一同时知道 worker / 起止 / 成败的地方。耗时取
`time.monotonic() - handle["run_time"]`。放在 `run_and_settle` 会绕过「登记项可能已被熔断清理」的
分支，故放在 `settle`。空观察者时 `emit` 早退，开销可忽略（`settle` 本就每完成一次做日志与结果投递）。

**成败判据**：`error is None and (result is None or result.success)`。只看 `settle` 的 `error` 会把
**失败一律记成成功**——`BaseWorker.run()` 捕获执行体异常后不外抛，而是把失败封进 `WorkerResult`
（issue #228），故 `settle(error=...)` 在 Worker 失败时根本不会走到。实现期由 `error_count` 恒零
暴露（见 tasks 6.4 的注入验证）。

### D3：指标身份 —— 以 Worker 的 `registry_name` 对齐

现状 `SVMWorker.register_worker(name, worker)` 以调用方传入的 `name` 为键；`Master._setup_svm` /
`Master.register_worker` 传入的是**注册表键**。而派发侧只能看到 `worker.registry_name`
（`BaseWorker` 自述的「无实例后缀身份」，也是结果响应器过滤所用的身份，issue #229）。

为使事实能命中 SVM 的指标条目（否则 `record_execute` 早退，仍恒为零——正是本 issue 要消灭的静默），
本变更统一以 `worker.registry_name` 作为指标身份：调用方按 `worker.registry_name` 注册，
`Master.get_worker_stats` 的健康查询同样按 `worker.registry_name` 取。默认 Worker
（`StateMachineWorker` / `EventWorker`）的注册表键与 `registry_name` 相同，对外可见的 key 形状不变。

### D4：SVM 作为接缝的**消费者**，而非内核特例

`SVMWorker.start_monitoring()` 注册 `self._on_execution`（转调既有 `record_execute`），
`stop_monitoring()` 注销。`enable_svm=False` 时不注册、不观察，零行为变化。

### D5：exporter 形态 —— 可选附加 `otel` + 零依赖可跑示例

`pyproject.toml` 新增 `[project.optional-dependencies].otel`（OTel SDK + OTLP exporter），
默认 `dependencies` 一字不动。`zoo_framework/observability/` 提供：

- `PrometheusTextExporter`：**仅标准库**，从接缝累加计数并渲染 Prometheus 文本格式。
- `OtlpMetricExporter`：**惰性 import** 上游；缺附加时抛出指名 `pip install zoo-framework[otel]`
  的显式错误（与 `native` 先例同形，不静默回退）。

`example/observability/prometheus_endpoint.py`（标准库 `http.server`，**不装任何附加即可跑通**）
与 `example/observability/otel_push.py`（需附加）各演示一条路径。

**为何 stdlib 可跑**：验收要求「至少一个 exporter 示例可跑通」。OTLP 上游在本机环境不可装 / 不可跑，
故可跑通的那一个选 Prometheus 文本端点；OTLP 路径以「缺附加显式报错」被守护。

## Risks / Trade-offs

- [SVM 指标 key 由注册表键改为 `registry_name`] → 默认 Worker 两者相同，对外不可见；自定义重命名
  注册（键 ≠ 类名）时 key 变为类名，比「恒零」更接近真值。已在 D3 说明。
- [Per-settle 解析进程级注册表带来一丁点开销] → `settle` 本就解析 `EventReactorManager`，同量级；
  无观察者时 `emit` 早退。
- [OTLP 路径本机不可跑，只有「缺附加报错」被守护] → 在 tasks / 报告中如实标注为未验证项，不谎称已跑通。
- [文档面较广（llms.txt / AGENTS / ARCHITECTURE / FAQ 口径）] → 由既有机械一致性测试（
  `tests/test_doc_consistency.py`、`tests/test_agent_discoverability.py`）兜底，漏改即红。

## Migration Plan

无数据/配置迁移。回滚即还原代码与文档；接缝与 exporter 都是新增面，删除不影响既有行为。

## Open Questions

（无。维护者已裁定四条；`tasks.md` §0 逐条记录采用值与依据。）
