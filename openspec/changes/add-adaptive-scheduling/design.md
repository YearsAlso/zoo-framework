# Design: add-adaptive-scheduling

> **⚠️ 状态：已延后（维护者 2026-10-09 决定）**——本文档为重启时的既有设计资产，不进入实施；
> 实施闸门与理由见 proposal.md 文首状态块。

## Context

见 proposal.md。架构定位：**训练与推理分离**。框架内只做「采集 + 加载 + 推理」（纯 stdlib、μs 级预算）；训练在独立项目进行（可用 numpy/sklearn，无框架依赖约束）。两者以**特征日志（JSONL）**和**权重档案（checkpoint）**两个文件契约连接。

技术地基（已存在，直接复用）：

- **结算收口**：`WorkerDispatchCore.settle`（登记先于派发、投递恰好一次）——特征采集挂点，只消费登记项
- **参数模式**：`@params` + `ParamsPath` 三段解析 + lazy import（`native:*` 先例）
- **持久化先例**：`PersistenceScheduler` 原子写 + 校验和 + 滚动备份——权重档案校验形态的参照
- **进程级状态**：`core/process_state.py` CARRIERS 登记复位表
- **native 线**：`NativeTaskWorker`/`NativeAdapter` 已就位；决策「native 臂」即派往它

## Goals / Non-Goals

**Goals**

- 框架内：特征提取 → 异步 JSONL 日志 → 权重加载校验 → 线性 softmax 推理，闭环两端都有文件契约
- fail-open：决策层任何异常不传导为任务失败
- 关闭（默认）时零影响：不进代码分支、不取锁
- 训练侧独立立项，不污染框架依赖

**Non-Goals**

- 框架内不做任何训练（含 SGD）——训练慢不构成框架内训练的理由，热路径预算只有一个推理点积
- 不改 `WorkerDispatchCore` / `ThreadPoolModel` / waiter 的既有语义
- 不做梯度下降在线更新权重（权重只来自训练项目产出，框架只读）
- 不自动增减 worker 数量（首版只决策 native vs 普通，池档位留扩展点）
- 「训练下沉 Rust」（NativeTaskWorker 消费训练）不在本变更，登记为 native 线后续候选

## Decisions

### D1: 训练/推理分离，两个文件契约

**选择**：框架 ↔ 训练项目之间只通过两个文件交流——
1. **特征日志**（JSONL，框架写，训练读）：每条记录 `{ts, worker, features, chosen, result, schema_v}`
2. **权重档案**（checkpoint，训练写，框架读）：`{format_v, schema_v, feature_names[], weights{}, checksum}`

**理由**：训练迭代节奏（小时级）与框架运行节奏（秒级）天然解耦，文件批式交换最简且可离线审计；框架不感知训练算法（torch/sklearn/手写 SGD 任换来），训练不感知框架内部结构——只依赖特征 schema。
**备选**：HTTP/RPC 在线喂样本（实时性强但引入服务Dependency与可用性问题）；SQLite 中转（多一个状态存储要管）。都过重，文件批式足够。

### D2: 特征 = 4 个 O(1) 统计量 + schema 版本化

**选择**：`duration_ms`（本次实测）、`error`（0/1）、`input_bytes`、`queue_depth`（派发瞬间读取）。特征名列表固定进 schema 版本（首版 `SCHEMA_V1 = ["duration_ms_ewma", "error_rate_ewma", "input_bytes", "queue_depth"]`）。TaskProfile 持有 duration_ewma / error_rate_ewma / input_bytes_ewma 供**推理时**使用；日志里同时记录**本次实测值**与 **EWMA 值**两类（训练用实测、推理用 EWMA，字段分开命名）。
**理由**：训练需要「单次真实样本」，推理需要「稳定的当前状态估计」——两者语义不同，混在一个字段会让训练学到的是平滑假象。

### D3: 推理 = 纯 stdlib 线性 softmax，权重字典点积

**选择**：`score(arm) = Σ w[arm][f] * x[f]`，两臂（native / default），softmax 归一后按概率采样（探索率可配，缺省小值）；`w` 是从 checkpoint 加载的 `{arm: {feature: weight}}` 字典。特征维度以 checkpoint 的 `schema_v` 为准，与 `SCHEMA_V*` 常量比对。
**理由**：stdlib 的 `math.exp` + dict 求和就是一次点积，µs 级；两臂 softmax 手写 10 行；不碰 numpy 红线。
**备选**：决策树 if-else 导出（表达力与训练复杂度都不匹配首版）；kNN 查样本表（内存与查询开销超预算）。

### D4: 权重档案校验 = PersistenceScheduler 同款三件套

**选择**：checkpoint 文件自带 `format_v`/`schema_v`/`checksum`；加载时校验 checksum（内容 hash）+ 版本比对，任一不符 → 显式拒绝（Logger 记录原因）→ 静态默认。支持 `adaptive:modelPath` 变更后的运行期重载：`reload()` 显式调用（首版不做后台周期检查，重载入口留给 CLI/手动）。
**理由**：与 `PersistenceScheduler` 的既有信任模型一致（坏文件显式拒绝不静默回退）；周期后台检查是不错的新增复杂度，重载入口先手动手动。

### D5: 特征日志 = 内存缓冲 + 批量追加

**选择**：`FeatureLog` 内部 list 缓冲，超过 `adaptive:logFlushThreshold`（默认 64 条）或显式 `flush()` 时追加写 JSONL（append 模式，单行一记录）；写失败捕获后清空缓冲并标记 degraded（本进程不再尝试写，避免每条日志都撞磁盘满错误）。
**理由**：热路径 O(1)（list.append + 阈值检查）；批量 IO 摊薄开销；degraded 标记防错误风暴。日志文件按追加语义无需原子写（丢尾部一批可接受，训练数据不怕少量缺失——不值得为它上 PersistenceScheduler 全套原子写）。

### D6: 接线点 = begin 前推理 + settle 后采集，两处仅消费不动语义

**选择**：
1. `WorkerDispatchCore.begin`（登记后派发前）→ `AdaptiveScheduler.decide(worker_name)`；决策写登记项扩展字段；异常 try/except 全包 → 默认路径
2. `settle` 尾部（投递完成后）→ `FeatureLog.record(...)`；try/except 全包

native 臂可用性 = `native:enabled=true`（与 adaptive 开关独立）；两者独立，推理选了 native 而 native 未启用时按普通路径走（不报错、记录实际路径便于训练纠偏）。
**理由**：最小挂点；记录「实际走的路径」让训练数据反映真实执行结果而非决策意图，训练才有正确标签。

### D7: 配置键族

`AdaptiveParams`（lazy import）：`ADAPTIVE_ENABLED = param("adaptive:enabled", False)`、`FEATURE_LOG_PATH = param("adaptive:featureLogPath", "adaptive_features.jsonl")`、`MODEL_PATH = param("adaptive:modelPath", "")`（空 = 无模型 = 恒默认）、`LOG_FLUSH_THRESHOLD = param("adaptive:logFlushThreshold", 64)`、`EXPLORATION = param("adaptive:exploration", 0.05)`（softmax 采样温度/ε 混合探索率）。

### D8: 线程安全

- `TaskProfile` 内 EWMA 更新与读取用 `threading.Lock`（临界区 O(1) 乘加）
- `FeatureLog` 缓冲 list 的 append/flush 用锁保护（flush 由触发线程执行，不另起后台线程——首版避免新线程）
- `AdaptiveScheduler` 权重引用是原子替换（重载时整体换 dict），读侧无锁
- 不用 ThreadSafeDict（multiprocessing.Lock 已被 bench 证伪）

## 独立训练项目边界

- 仓库形式：独立 repo（zoo-bench 形态先例），**命名待维护者确认**（候选 `zoo-adaptive-trainer`）
- 职责：读特征 JSONL → 特征工程 → 训练 softmax 回归（可用 numpy/sklearn）→ 写 checkpoint（含 checksum 与 schema_v）→ 可选评估报告
- 依赖契约：特征 schema 由框架侧 `SCHEMA_V*` 常量定义并写入每条日志记录；训练项目按 schema_v 识别字段，跨版本必须能识别并拒绝不认识的 schema
- Rust 训练下沉：训练作为原生任务挂 NativeTaskWorker——登记到 `add-native-task-execution` 的后续候选，不在本变更

## 维护者决定记录（2026-10-09）

1. **ML 线延后**（proposal 文首状态块）：首个决策（native vs 普通）已被实测包络规则覆盖；
   特征空间小、臂少，bandit 与离线 ML 决策质量差距小而链路成本差距大。
2. **特征导出机制 = 该线的必要前提**（设备间模型不互通用 → 训练数据只能来自框架运行期）：
   - 采集挂点 `settle`（结算收口是决策上下文与观测结果唯一同时可见的位置，配对完整性由此保证）；
   - 方案 A 候选 = 结算点 JSONL 配对导出（决策上下文快照 + 结算观测结果，按设备/任务键分组，
     同一日志流按 key 分组即各设备的独立训练集）；默认关闭、独立线程落盘；
   - 被**否决**的形态：经事件管道导出（通道重试/丢失语义会污染训练数据）、只读聚合 API
     （无逐决策配对，策略学习信号丢失）；
   - **train/serve 一致性硬约束**：导出的特征必须是模型上线时调度器真实拿到的那批特征。
3. **stdlib bandit 是已评估的简化替代**（重启时可先落地）：ε-greedy ~1µs / softmax 2–5µs，
   数百次决策收敛，可实时适应负载漂移；checkpoint 文件契约可与本 design 的权重档案共用。

## Risks / Trade-offs

- [推理进热路径] → 一次点积分支数 O(特征数=4)，µs 级；bench 验收断言延迟增量 < 2µs
- [特征日志写放大] → 缓冲批量 + degraded 标记；日志路径可关（`adaptive:featureLogPath=""` 禁采集仅推理）
- [训练数据标签噪声（路径选择影响时长）] → 日志同时记 chosen 与实际 path；训练侧可用反事实修正（off-policy correction），首版训练项目先记录问题不实现修正
- [权重漂移把好任务带歪] → 探索率保守缺省 + native 未启用时退化保底；关闭键即回滚
- [未登记 CARRIERS 被测试拦截] → 实施时同步登记 AdaptiveScheduler / FeatureLog 进 process_state.CARRIERS

## Migration Plan

1. 合入后默认 `adaptive:enabled=false`，框架零变化
2. 开启后无 `adaptive:modelPath` → 纯采集模式（只写特征日志不推理）——积累训练数据
3. 独立训练项目训练产出 checkpoint → config 设置 `adaptive:modelPath` → 重载生效
4. 回滚 = 关 `adaptive:enabled`

## Open Questions

- 特征日志轮转（按大小切分）首版是否做——倾向不做（训练数据量小），留观察
- `zoo-adaptive-trainer` 仓库什么时候立项、chohost 在哪——维护者裁决；框架侧文件契约已就绪即可随时开始
- off-policy correction 是否进首个训练版本——倾向先记问题不做
