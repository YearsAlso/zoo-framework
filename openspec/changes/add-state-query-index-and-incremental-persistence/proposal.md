# Proposal: add-state-query-index-and-incremental-persistence

## Why

GitHub issue #236：用 zoo-code-agent 做消费者时，状态层装不下"上下文记忆"——它是**快照层**（快照 / 崩溃恢复 / 变更观察），不是**文档 / 检索层**。维护者已裁定边界（2026-10-14）：内核只做四条原语，"记忆层"本身属消费方（zoo-code-agent#37 / #41）。

本变更是该拆分中的 **A2**，只做**读模型与持久化**接缝上的两条原语：

- **`StateIndex` 可插拔接缝已有，但没有任何带查询能力的默认实现**：`StateIndexFactory.register_index_type` 存在，`StateIndex` ABC 只有 `get/set/remove/has/get_all/find_by_prefix`，内置实现是线性前缀扫描。要按节点值找东西，只能把整表捞出来自己过滤。
- **持久化对整表 `deepcopy + pickle`，无脏跟踪、无淘汰 / TTL**：每次落盘把**全部**作用域重写一遍，改一个 scope 的代价与改全部 scope 相同；长期运行的作用域集合只增不减。

原语 1 / 4（追加、CAS）落在另一条接缝（写路径契约）上，由 A1 `add-state-append-and-cas` 承接。

## What Changes

- **原语 2（查询型索引默认实现）**：`StateIndexFactory` SHALL 内置一个支持按节点值查询（谓词 / 关键词过滤）的默认索引实现，并经既有注册接缝按名选取；索引类型 SHALL 可由新配置键 `stateMachine:indexType` 选择，默认 `"dict"`（现状）。内核 MUST NOT 内置语义 / 向量检索。
- **原语 3（增量持久化 + 淘汰 / TTL）**：持久化 SHALL 支持"只写脏作用域"模式（未修改的作用域不被重写），并 SHALL 支持按作用域 TTL 过期。二者均以新配置键启用，默认 MUST 保持现状（整表落盘、不淘汰）。
- **新增配置键默认值 MUST 保持现状**：`stateMachine:indexType="dict"`、增量持久化开关关闭、TTL 关闭。
- **不改变**：`set_state` / `get_state` / 观察者注册与注销 / effect 并发执行与有界等待 / `load_state_machines` 的整表替换恢复语义 / pickle 文件格式（未启用新能力时）。
- **不改 `StateIndex` ABC 的抽象方法集**：新增能力走该实现的**具体方法**，避免第三方已注册索引因未实现新抽象方法而实例化失败。

## 依赖：本变更依赖 A1

本变更**依赖** `add-state-append-and-cas`（A1）已合入，理由：

1. **版本语义**：A2 不做版本相关改动，但脏记账与 TTL 时间戳要挂在 A1 已修正的节点写路径旁；若 A1 未合入，写路径仍有版本双属性缺陷，测试会出现与 A1 相同症状的失败，难以区分归属。
2. **scope 级锁**：A1 引入的 `StateScope._mutation_lock` 是"写入时标记脏"的临界区载体。A2 的脏标记若不经该锁，会与 A1 的写路径产生竞态。
3. **改动面重叠**：A1 与 A2 都要改 `state_machine_manager.py` 与 `state_scope.py`，同树顺序落地比分叉后合并更稳。

**共享契约（A1 定义、A2 遵守）**：节点版本的严格递增语义与 `get_version()`；`StateScope._mutation_lock` 作为写路径临界区。

## 变更粒度取舍（拆 vs 合）

维护者已裁定**拆成两个变更**（2026-10-14），理由按项目规约的优先级 **架构一致性 > 业务逻辑连续性 > 开发量最小**：

- 两条接缝（**写路径契约** vs **读模型与持久化布局**）本就可分离，按接缝拆成两个各自自洽的变更；
- A1 单独合入即解阻塞消费方最迫切的两条，不依赖持久化布局变更；
- A2 是**最高风险块**（持久化布局变更 + Windows 原子替换语义 + `picklePath` 语义随开关而变），隔离在独立变更内可独立评审与回滚；
- 存在"只落 A1 不落 A2"的中间态，该中间态**仍自洽**：追加 + CAS 可用，只是仍整表落盘。

| 变更 | 覆盖原语 | 接缝 | 估算 |
|---|---|---|---|
| A1 `add-state-append-and-cas` | 1 追加 + 4 CAS | 写路径契约 | ≈ 4 文件 / 250–400 行（含测试） |
| **A2（本变更）** | 2 查询型索引 + 3 增量持久化 / TTL | 读模型与持久化布局 | ≈ 5–7 文件 / 400–700 行（含测试与文档） |

## Capabilities

### New Capabilities

无。两条原语均为状态层既有行为的扩展，落在既有 `state-machine` 能力内。

### Modified Capabilities

- `state-machine`: 新增两条 Requirement（状态索引的查询能力默认实现、持久化的只写脏作用域与按作用域 TTL 淘汰），并新增配置键。既有 Requirement（键路径写入语义、观察者注册 / 注销、effect 线程原语、持久化恢复）**不改动**——本变更以 ADDED 形式追加，未启用新能力时既有条款逐条仍成立。

## Impact

- **代码**：`zoo_framework/statemachine/state_index_factory.py`（新增查询型索引实现并注册）、`zoo_framework/statemachine/state_machine_manager.py`（脏作用域记账、`evict_expired_scopes`、按配置建 scope 时选索引类型）、`zoo_framework/statemachine/state_scope.py`（`last_modified` 时间戳）、`zoo_framework/workers/state_machine_work.py`（按配置决定落盘方式与淘汰）、`zoo_framework/params/state_machine_params.py`（新增配置键）。
- **配置**：新增 `stateMachine:indexType`、增量持久化开关、`stateMachine:scopeTtlSeconds`（键名与默认值以 design.md 为准），默认值全部保持现状。
- **文档**：`docs/`（状态一节）说明新原语、启用开关与默认值、TTL 时间基准、查询型索引的朴素定位与弱一致语义；`CLAUDE.md` 状态层注释；相关类 docstring。
- **测试**：新增 `tests/test_state_index_query.py` 与 `tests/test_state_incremental_persistence.py`（查询命中 / 空结果 / 并发、脏作用域门控、TTL 淘汰幂等、未启用时向后兼容、落盘失败显式化）。
- **兼容性**：未启用新能力时，`set_state` 等既有入口的行为与合入前一致，pickle 文件格式不变。
- **风险**：增量持久化的文件布局与 `picklePath` 的语义（文件 ↔ 目录）是最高风险点，见 design.md 的 Open Questions；TTL 的时间基准（墙钟 vs 单调钟、重启后语义）同样需明示。
- **依赖**：无新增第三方依赖；但**依赖 A1 合入**（见上）。
- **issue**：#236（本变更回复其中原语 2 与 3 的落地部分）。
