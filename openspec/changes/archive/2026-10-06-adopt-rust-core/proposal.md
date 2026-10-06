## Why

项目方向是「高性能、易用的 Worker / Server 框架」，Rust + Python 混用是该方向的候选架构。但当前**没有任何数据支撑这个决策**：

- 已有评审只证明了"用 Rust 替代 Python **调度层**收益很小"（边际 1–2 µs），**未回答**"Rust 承担 **I/O 与协议层**能拿回多少"
- 未在任何真实负载上测量"框架自身开销占端到端延迟的比例"——而这是决定 Rust 是否值得的唯一指标
- PyO3 边界的实际穿越开销、panic 的崩溃隔离可行性、构建与发布从 `hatchling` 迁移到 `maturin` 的代价，三者均未验证

在没有这些数据的前提下启动 Rust 迁移，等于把数月工程押在一个未验证的假设上。同时 `zoo-framework 0.5.3-beta` 已发布到 PyPI，其调度与 Worker 模式存在 4 个 P0 语义缺陷（由 `fix-worker-scheduling` 承接）——在语义尚未修正时迁移，会把错误一并搬迁。

本变更把「要不要做」与「怎么做」分离：先用最小代价把决策所需的数据测出来，再决定是否投入实施。

## What Changes

本变更**不修改任何运行时行为**，产出一组可复现的测量数据与一份 go / no-go 决策。

**测量与探针（产出物，非产品代码）**

- 构建最小 PyO3 探针扩展，实测三件事：边界穿越开销、`Python::allow_threads` 的释放/重获代价、Rust 回调 Python 的真实成本（不依赖公开基准，直接在本机测）
- 在同一台机器上对照两种执行模型：当前 `core/waiter/` 的轮询式调度 vs 最小 Tokio 反应堆 + 每请求一次边界穿越
- 以真实业务负载对现有框架做 profile，测量「框架自身开销占端到端延迟的比例」与「Worker 体执行时间中位数」

**决策文档**

- 基于实测数据给出 go / no-go / 部分 go 的结论，并明确"部分 go"时 Rust 从哪一层切入
- 若结论为 go，输出实施变更 `adopt-rust-core-impl` 的 proposal；**本变更不含任何实现**

**需要在本变更中定稿的前置约束（写入 design.md）**

- PyO3 边界收敛为唯一穿越点，且对单次请求的穿越次数给出上界
- Rust panic MUST NOT 导致 Python 进程 abort
- 构建发布从 `hatchling` 迁移到 `maturin` 的路径、wheel 矩阵与**可回退性**要求

## Capabilities

### New Capabilities

无。本变更不修改任何运行时行为——它产出的是测量数据与决策文档，属 OpenSpec 规范中"pure refactor, tooling, docs"一类，已在 `.openspec.yaml` 中以 `skip_specs: true` 声明。

### Modified Capabilities

无。理由同上：本变更不产生 spec 级的行为变化。真正的行为变更（若决策为 go）由后续的实施变更承载，届时按目标架构建立 spec 基线。

## Impact

| 类别 | 内容 |
|---|---|
| 新增（非产品代码） | `bench/` 下的 PyO3 探针与基准脚本；PoC 用的最小 Tokio 反应堆 |
| 不修改 | `zoo_framework/` 下任何运行时模块；`pyproject.toml` 的构建后端（迁移方案只写入 design，实施留待后续变更） |
| 不修改 | `.github/workflows/` 的任何发布流程 |
| 依赖 | **`fix-worker-scheduling` 的验收结果**——需要一个语义正确、行为可复现的 Python 实现作为对照基线。否则测量对照的是错误行为，结论无效 |

**为什么必须先完成 `fix-worker-scheduling`**：本变更要回答的核心问题是"框架开销占端到端延迟多少"。若基线实现本身存在"瞬时 Worker 永久停摆""`is_loop` 语义失效"这类缺陷，测出的"开销"既包含真实成本也包含缺陷造成的退化，无法作为决策依据。此外，本机实测已显示当前框架 90% 以上的性能问题源于 Python 层的实现选择（`concurrent.futures` 记账、`multiprocessing.Lock`、`gevent` 包装），这些在 `fix-worker-scheduling` 中被修复后，基线数字才是公允的。

**范围边界**

- 不实现任何产品级 Rust 代码，不引入 Rust 运行时依赖
- 不改动已发布版本的任何行为
- 不预设结论为 go；本变更的合法产出包括"no-go，维持纯 Python"
