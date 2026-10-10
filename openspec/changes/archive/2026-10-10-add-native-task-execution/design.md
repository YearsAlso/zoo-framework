# design — add-native-task-execution

## Context

框架现状态（dev @ `331bba3`，0.9.2-beta）已具备承接原生执行的原语：`WorkerDispatchCore` 提供单一结算收口（`run_and_settle → settle`，盖章 run_id/session_id 于登记项）、在飞表 + RLock、超时观测与熔断、停机回收；`ThreadPoolModel` 已去掉 Future 记账（固定线程 + `queue.Queue`）；`run-identity` 经 `carry_context` 显式跨越线程边界。历史 no-go（`bench/DECISION.md`）针对的是「Rust 派发 Python callable」，与本变更的「原生执行体本身」不同——后者尚未测量。

约束：
- **可选扩展**：主包保持 hatchling / 纯 Python；Rust 工具链不进主依赖。
- **可撤回**：小组件、每阶段产物可独立停用；不给未来需求预留通用运行时。
- **契约隔离**：内核不 import PyO3/Tokio；绑定与转换全部在外围适配器。
- bench/ 目录为冻结的历史证据区，不修改、不冒充业务实现。

## Goals / Non-Goals

**Goals:**
- 定义一个小的语言无关执行契约（任务描述、输入输出格式、错误分类、能力查询），使 Rust 扩展只依赖契约而不依赖框架对象。
- 提供 `NativeTaskWorker`（挂进既有调度/结算/熔断生命周期的一条新 Worker 形态）与原生适配器两个 Python 组件。
- 提供可选 Rust 扩展包，含契约版本握手、能力清单、首个真实任务实现。
- 阶段化推进，阶段 0（选真实任务 + go/no-go 门槛确认）不满足就不进入实现。

**Non-Goals:**
- 不做 Tokio 常驻运行时、sidecar 进程隔离、零拷贝承诺、原生内部并行。
- 不改 `delay_time`、唤醒、参数解析、事件协议、pickle 格式的既有语义。
- 不建第二套调度/状态/结果簿记（沿用 `WorkerDispatchCore`）。
- 不重写冻结的 `bench/` 历史。

## Decisions

### D1 — 契约的形态：Python 侧协议类 + Rust 侧同名常量表

契约在 Python 侧是 `NativeTaskContract`（数据类：`name`、`contract_version`、`input_format`、`max_input_bytes`、`output_format`、`error_classes`、`capabilities` 元组）；Rust 扩展暴露 `contract_version() -> int` 与 `capabilities() -> list[str]`，适配器加载时逐字段比对帧 Exclude 判据。选择协议类而非抽象基类的理由：契约是**数据**而非多态——native 侧只回传常量，无子类派发需求；比 ABC 却多出「直接可序列化」的便利。
备选：JSON Schema 声明（否——引入 schema 校验依赖，且首版只有一个消费者）；PyO3 alleged pyclass 直接注册（否——内核被反向依赖）。

### D2 — 执行入口：`NativeTaskWorker._execute()` → 适配器 → Rust

`NativeTaskWorker(WorkerProps)` 声明 `task_name`，构造时注入适配器（默认取模块级单例 `get_native_adapter()`，测试可注入 fake adapter）。`_execute()`：`adapter.prepare_input(props, run_identity)` → `adapter.execute(task_name, input)`（此调用体内 RUST 释放 GIL，经由 PyO3 `Python::detach`，固定版本后按该版本实施）→ 产出值交回 `BaseWorker.run()` 的返回值，走既有 hooks 与 `WorkerResult`。
选择「一个 worker 类 + 注入 adapter」而非「每任务一个子类」：首版只有 1 个真实任务，抽象多子类的成本无收益；因而 fake-adapter 单测也可驱动生命周期而不需要真实扩展。

### D3 — 错误映射：受控错误 → Python 异常类型三族；panic → 单一兜底

Rust 侧错误枚举分三族：`InvalidInput`（拒绝，执行前转换失败）、`TaskFailed`（业务失败，运行中），`Panic`（unwind 在任务边界兜底）。适配器按族映射为三个 Python 异常类（`NativeInvalidInput` / `NativeTaskFailed` / `NativePanic`），均继承一个 `NativeTaskError` 基类；Worker 的 `_on_error` hook 捕获后交 `settle(error=...)`，同族语义不变。
备选：Rust 侧返回 `Result` 值而非抛异常（否——把错误塞进成功结果会把「错误伪装成成功空结果」的风险重新引入，违背 proposal 的正确性第 2 条）。
显式声明：`catch_unwind` **不是进程隔离**——abort / 段错误 / OOM 仍打穿进程；这是首版接受的同进程边界。

### D4 — Rust 扩展的物理位置：树内独立子目录 `native/`，独立构建配置

`native/`（不进 wheel 主包，hatchling 配置 exclude）含独立 `pyproject.toml` + maturin 构建后端 + 固定版本的 `Cargo.toml`。选树内子目录而非独立仓库的理由：与 bench/pyo3_probe 相仿的仓库生命周期（随 dev 主干演进），但物理与构建产物均独立；独立仓库则 CI / 打开两个仓库的成本更高且收益未显现（首版只有一个任务）。
备选：独立仓库（否——与 zoo-bench 的「树外」先例不同，该先例的理由是「框架仓库从来不需要它的代码」，此处置此处不成立）；tree 内与主包同构建配置（否——把 maturin 塞进 hatchling 会把 Rust 工具链变成用户安装成本）。

### D5 — 注册与运行期接入：复用 `WorkerRegistry` + `core.add_worker`

构造期注册走 `Master.register_worker`（可无参构造限制在接入文档中写明解决路径：工厂闭包，与 zoo-code-agent 的用法一致）；运行期注册经 `WorkerRegistry.register_instance` + 显式 `core.add_worker`（调度列表由内核持有，仅在注册表登记不足以被派发——`dispatch_core.py` docstring 明言）。MUST NOT 重开 legacy `@worker` 路径。

### D6 — 配置：独立键族 `native:*`

新 `zoo_framework/params/native_params.py`，三段解析与既有键族一致；`native:enabled`(默认 False)、`native:contract_version`、`native:tasks`（任务名 → 配置映射）。lazy import 维持既有纪律（`Master._create_waiter` 等处已有先例），避免 `ParamsFactory` 未读 config 前冻结默认值。

### D7 — 阶段 0 门槛

首版实施前须：
1. 选定 1 个真实消费者热点任务（候选来源：zoo-code-agent 工具循环里的解析/校验/聚合，或设备场景的协议解析）；
2. 完整链路剖析（同一次运行内分段采集，遵守 bench/ 三条硬约束读数纪律）；
3. 维护者确认最低可接受端到端收益与维护成本，写进 `native/DECISION.md`（沿用 bench/DECISION.md 的格式惯例）。
未达门槛 → 如实记录 no-go，变更不归档为「已实现」，tasks 以「阶段 0 未通过」收尾。

## Risks / Trade-offs

- [转换成本吃掉原生收益] → 契约把转换留边界且首版选粗粒度/批量任务；阶段 0 剖析单列转换耗时。
- [同进程崩溃牵连 Python] → 明示 `catch_unwind` 只是 unwind 兜底；错误映射留痕。
- [线程池嵌套超额并发] → 首版复用现有池、一个池线程一个原生任务；引入原生内部并行前须先统一 CPU 并发预算。
- [第二套簿记分叉] → 周期/熔断/结算全部留在 `WorkerDispatchCore`，Rust 侧不重实现。
- [构建矩阵/ABI 漂移] → 扩展包自身固定 PyO3/cargo 版本；版本提升属扩展包变更，不碰框架。

## Migration Plan

1. 阶段 0：产出 `native/DECISION.md`（任务选定 + 剖析数据 + go/no-go 结论）——**用户确认后**才开工 D2/D4 的实现。
2. 实现：按 tasks.md 顺序（契约 → 适配器 → worker → extension → 集成 Registrar）。
3. 验收：spec 的 Scenario 逐条覆盖测试；native 扩展仅在有工具链的环境运行（pytest skipif）。
4. 回滚：`native:enabled=False`（默认即 False）即整体停用；删 `native/` 与 `zoo_framework/native/` 即可完全撤回，不触碰既有代码路径。

## Open Questions

- 首个真实业务任务与语义等价样本：**阶段 0 事项，未定**（需维护者确认候选）。
- 原生扩展包名 / 版本策略（e.g. `zoo-framework-native` 与主包版本是否锁定耦合）：阶段 0 后、阶段 3 前定。
