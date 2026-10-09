# Proposal: add-adaptive-scheduling

> **⚠️ 状态：已延后（Deferred，维护者 2026-10-09 决定）**
>
> ML 自适应调度线**无限期延后，暂不实施**。理由：
>
> 1. 首个二元决策（native vs 普通）的大头已被实测包络规则覆盖（帧 ≥21 字节路由原生，
>    2.8x–9.7x，见 `native/DECISION.md`），规则可写出的关系不构成 ML 的增量；
> 2. 特征空间仅 4 维、决策 2 臂，μs 级 stdlib bandit（ε-greedy/softmax）与离线训练
>    softmax 的决策质量差距小，而 ML 多出整条训练链路（独立项目/日志消费/权重运维/换设备重训）；
> 3. ML 的优势场景（多任务类别混跑、负载频繁漂移、跨任务泛化）当前无证据存在。
>
> 重启条件触发时（上述场景出现），本变更的规划文档直接复用。两个遗留结论随重启保持有效：
>
> - **特征导出机制是该线的必要前提**（不同设备需重训 → 训练数据只能来自框架运行期；
>   采集挂点在 `settle`，方案 A 候选 = 结算点 JSONL 配对导出，见 design「维护者决定」节）；
> - stdlib bandit 是已评估过的简化替代（一次点积 μs 级、数百次决策收敛、可与权重档案
>   共用文件契约）——重启时可先以 bandit 落地，ML 仅在特征空间扩张后再评估。

## Why

当前框架的调度决策是**静态的**：worker 进哪个池、native 开不开，全由 config.json 在启动时冻结，运行期任务负载形态变化（CPU 密集与 IO 密集混合、热任务漂移）时无法响应。阶段 0 实测（本机 5900X）已证明 native 释放 GIL 有 5.87x@12 并发的真实多核伸缩，但收益被任务形态稀释（小任务 4–7x、C 库顶住的任务 1.5–3x）——**收益高度依赖任务与负载形态，而形态只能运行期观测**。需要一层基于 ML 的自适应决策：框架内运行期**采集任务特征日志**，独立训练项目**离线训练调度模型**，框架**加载训练参数（权重）做在线推理**选择「native vs 普通」，使调度决策跟随负载形态而非启动时拍板。

维护者已明确保留 ML 方案（否决纯 bandit 单方案）：训练参数必须可累积、可持久化；训练侧独立立项（zoo-bench 先例：独立仓库），训练消费特征日志、产出权重档案；后续可把训练任务经 `NativeTaskWorker` 下沉 Rust（被 `add-native-task-execution` 阶段 0 闸门阻塞，非首版必需）。
**（2026-10-09 更新：维护者重新评估后决定延后整条 ML 线，见文首状态块。）**

## What Changes

- 新增 `zoo_framework/core/adaptive/` 模块：ML 调度决策层（推理侧）
  - 特征提取（时长 EWMA、错误率、输入尺寸、队列深度）→ 模型输入向量
  - **特征日志采集**：结算后异步追加 JSONL（缓冲批量写），供训练项目消费
  - **模型权重加载**：checkpoint 文件（版本 + 特征 schema 版本 + 校验和），缺失/损坏/版本不匹配 → 显式拒绝并退静态默认
  - **在线推理**：纯 stdlib 线性 softmax（一次点积，μs 级），输出 native/普通选择
  - 保守默认 + 冷启动兜底：无模型时与现有静态调度行为一致（回归保障）
- 新增参数键族 `adaptive:*`（`adaptive:enabled` 默认 **false**，lazy import 纪律同 `native:*`）
- 新增**独立训练项目**（不在本仓库，zoo-bench 同形态）：消费特征日志 → 训练（可用 numpy/sklearn，无框架依赖约束）→ 产出权重档案
- **不改变**静态调度为缺省行为：关闭开关时框架一切如旧（零回归路径）
- 框架内零新第三方依赖（推理纯 stdlib：`math`/`threading`）

## Capabilities

### New Capabilities
- `adaptive-scheduling`: ML 自适应调度决策。SHALL 采集特征日志、SHALL 加载并校验训练权重、SHALL 用权重在线推理选择执行路径，SHALL 在无模型/校验失败/证据不足时退回静态默认，MUST NOT 在关闭时改变既有调度行为。

### Modified Capabilities

无——`worker-scheduling` / `scheduler-model` / `native-task-execution` 的既有 REQUIREMENTS 不变；自适应层是叠加观测/决策层，不改既有调度语义（dispatch 仍经 `WorkerDispatchCore` 单一结算收口）。

## Impact

- **代码**：新增 `zoo_framework/core/adaptive/`（新模块）、`zoo_framework/params/adaptive_params.py`、`params/__init__.py`（导出）
- **接线点**：`WorkerDispatchCore.begin` 前查询决策、`settle` 后采集特征日志（不改 settle 语义，仅消费已登记项）
- **依赖**：框架内零新第三方依赖；训练项目独立管理自身依赖（不进 `pyproject.toml`）
- **测试**：`tests/test_adaptive_scheduling.py`（特征、日志、权重加载校验、推理、冷启动回归、关闭时零影响）
- **风险**：决策/日志进入 dispatch 热路径——推理 μs 级、日志异步缓冲；全部 fail-open
- **与 native 线的关系**：独立 change 不阻塞；「训练下沉 Rust」是 `add-native-task-execution` 的潜在后续消费方（训练作为原生任务挂 NativeTaskWorker），不含在本变更内
