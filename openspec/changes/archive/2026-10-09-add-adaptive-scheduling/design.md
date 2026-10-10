# Design: add-adaptive-scheduling

## Context

见 proposal.md。架构定位：**在线自学决策，全部在 Worker 自身生命周期内闭环**。没有训练项目、没有特征日志、没有权重档案——统计状态就是代码里的两个浮点均值。

技术地基（已存在，直接复用）：

- **Worker 生命周期**：`BaseWorker.run()` → `_execute()` → hooks → `WorkerResult`；`is_loop` / `run_timeout` / `delay_time` 属性契约
- **单一结算收口**：`WorkerDispatchCore.settle`——本变更不碰它，`DualArmWorker` 的双臂执行体结果照走既有结算
- **native 线**：`NativeTaskWorker` / `NativeAdapter` 已就位；原生臂可用性经 `native:enabled` + 适配器握手（缺失时按该能力的显式拒绝路径，不静默回退）
- **参数模式**：`@params` + `ParamsPath` 三段解析 + lazy import（`native:*` 先例）
- **进程级状态**：`core/process_state.py` CARRIERS 登记复位表

## Goals / Non-Goals

**Goals**

- `DualArmWorker`：用户子类声明 python 臂与 native 臂（`_execute_python()` / 原生 task_name），基类在 run() 内「决策 → 计时 → 更新」，调度内核零改动
- 奖励 = **实测执行时长**（秒，越小越优）；增量式均值更新（O(1)，无样本存储）
- ε-greedy 探索（默认 0.05）；统计持久化可选（JSONL 快照，`adaptive:statsPath`，默认空 = 不持久化——重启后统计清零，冷启动阶段成本可接受）
- fail-open：决策层任何异常不传导为任务失败（双臂异常照既有 `_on_error` → 结算收口）
- 关闭（默认）时零影响：不进代码分支、不取锁

**Non-Goals**

- 不做 contextual / softmax / 权重点积——特征向量维度与非线性关系当前无证据
- **不做任何训练/导出机制**（ML 线已不推进；bandit 的"训练"就是运行时的均值更新本身）
- 不改 `WorkerDispatchCore` / `ThreadPoolModel` / waiter / `native-task-execution` 的语义
- 不自动增减 worker 数量、不动池档位（首版决策仅双臂路由）
- 不做决策审计流（日志只记一行 INFO，不上结构化遥测）

## Decisions

### D1: bandit 形态 = 逐任务类 ε-greedy（维护者选定）

**选择**：每任务类两臂均值的增量式 ε-greedy。`EpsilonGreedy` 持 `{arm: (n, mean)}`，决策 O(1)（`argmax` 均值，ε 概率随机探索），更新 O(1)（增量均值 `mean += (r - mean) / (n + 1)`）。
**理由**：决策问题就是"哪个臂平均更快"——均值比较直接表达它；无特征 schema（这正是 ML 线的成本所在）、无探索超参调优负担（单 ε）。
**备选**：softmax 按概率采样（否——引入温度超参，收益与 ε-greedy 无异）；UCB1（否——置信上界对延迟抖动比均值更敏感，首版不需要）。

### D2: 接线 = `DualArmWorker` 基类内闭环（维护者选定，否决内核挂点）

**选择**：新基类挂 `zoo_framework/workers/`，`_execute()` 内：

1. `policy.decide(self.name)` → `"native" | "python"`；
2. native 臂可用性检查（`native:enabled` + 适配器），不可用 → 本次按 python 臂执行**并记录实际臂**（纠偏数据就是统计更新本身）；
3. 计时执行对应臂 → `policy.record(self.name, arm, duration)`；
4. 声明周期 hooks (`_on_error` / `_on_done`) 照 `BaseWorker` 契约走到。

**理由**：
- **零内核改动**——`WorkerDispatchCore` / 模型 / waiter 完全无感知，既有 <2µs 派发预算验收任务（tests/test_worker_scheduling.py）零回归风险；
- **决策与奖励天然同处**——双臂计时就是奖励观测，不存在 old design 里"begin 决策 / settle 采集"两处的配对维护成本；
- **决策粒度恰好正确**——逐 worker 类统计，正对应"逐任务类路由差异"的实际数据形态。
**备选**：`begin/settle` 全局挂点（否——改热路径、决策/奖励分离两处、正确性测试面大；只有当决策需要覆盖"未声明双臂的普通 Worker"时才有必要，而那违反"不猜测"原则）。

### D3: native 臂不可用时的语义 = 显式拒绝，不静默回退

**选择**：声明了原生臂但 `native:enabled=false` 或扩展缺失时，`DualArmWorker` 构造期/首轮即显式报错（复用 `NativeAdapter.ensure_ready` 的 `NativeInvalidInput` 族）。
**理由**：与 `native-task-execution` 的「不静默回退」规格一致——静默回退 python 臂会把「配置错误」伪装成「自适应决策」，统计再无纠偏意义。用户显式声明了双臂，说明意图就是用原生能力。
**备选**：自动退化 python 臂（否——见上）。

### D4: 统计持久化 = 可选 JSONL 快照（与 ML 权重档案彻底不同物）

**选择**：`adaptive:statsPath` 默认空 = **不持久化**。显式配置时，进程内统计以 JSONL（每次 flush 全量快照，原子写 + 校验和——PersistenceScheduler 三件套先例）形式落盘，重启后加载作为先验。
**理由**：持久化是可选增强而非能力前提（与 ML 线的"无导出则训练无从谈起"本质不同——bandit 冷启动只需几百次贴脸执行即可收敛，期间损失可量化且有限）。首版可直接不实现落盘（键声明了但 `""` 默认无消费者风险）——**首版实现**：键有消费者，代码路径 ~40 行。
**备选**：完全不提供持久化（否——长跑进程重启后统计清零的成本用户自担，可选开关是低成本必需品）。

### D5: 参数键族（对 ML 版简化）

`AdaptiveParams`（lazy import）：`ADAPTIVE_ENABLED = param("adaptive:enabled", False)`、`EXPLORATION = param("adaptive:exploration", 0.05)`、`STATS_PATH = param("adaptive:statsPath", "")`（空 = 不持久化）。ML 版的 `featureLogPath` / `modelPath` / `logFlushThreshold` 三键**不再声明**（bandit 无对应物，死键不进配置面）。

### D6: 线程安全

- `EpsilonGreedy` 的统计更新/读取由单 `threading.Lock` 保护（临界区 O(1) 乘加-read）
- `BanditPolicy` 按 worker 名持 `EpsilonGreedy` 实例（dict 索引在 CPython 是原子的；新增类目在锁内)
- 不用 ThreadSafeDict（multiprocessing.Lock 已被 bench 证伪）
- 同名 `DualArmWorker` 的多实例共享统计（这正是"逐类学习"的语义；`num` 后缀只进日志名，不进统计 key——key = 类名）

## Risks / Trade-offs

- [原生臂执行抖动被误学为均值] → ε 恒定探索 + 增量均值对旧样本自然衰退（`1/(n+1)` 衰减），漂移可跟随
- [决策对 worker 类有记忆但对运行环境无感知] → 首版接受；环境剧变时统计逐步自我修正
- [DualArmWorker 子类双臂语义不对等（输出不同构）] → 文档明示两条臂 MUST 语义等价（同一任务结果的两种实现），否则统计无意义
- [统计 key 撞名] → key = 类名 + `native:task:name`（python 臂与 native 臂天然不同名不会撞）
- [未登记 CARRIERS 被测试拦截] → 实施时登记 BanditPolicy 进 process_state.CARRIERS

## Migration Plan

1. 合入后默认 `adaptive:enabled=false`，框架零变化（零回归路径）
2. 需求方继承 `DualArmWorker` 声明双臂 + 开 `native:enabled` + 开 `adaptive:enabled` → 自动开始逐类学习
3. 回滚 = 关 `adaptive:enabled`（统计丢失可接受）或不继承基类

## Open Questions

- 双臂奖励的直接可比性：python 臂实测时长与 native 臂实测时长均为 wall-time（同进程同负载语义），无归一化问题——首版接受；若将来不同量纲任务混入，届时再评估归一化
