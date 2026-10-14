# Proposal: add-state-append-and-cas

## Why

GitHub issue #236：用 zoo-code-agent 做消费者时，状态层装不下"上下文记忆"——它是**快照层**（快照 / 崩溃恢复 / 变更观察），不是**文档 / 检索层**。维护者已裁定边界（2026-10-14）：内核只做四条原语，"记忆层"本身属消费方（zoo-code-agent#37 / #41）。

本变更是该拆分中的 **A1**，只做**写路径契约**的两条原语——消费方最迫切、且彼此同源（都依赖"节点版本可用作乐观并发控制"这一前提）：

- **写入粒度是整值替换**：往一个集合键里加一条，必须读出整个集合、改、再整体写回，单条追加 O(n)，累计 O(n²)。
- **同 scope 跨线程 read-modify-write 会丢更新**：`StateNode.version` 字段存在，但入口不暴露条件写，且该字段本身有缺陷（取值是秒级 `int(time.time())`，同一秒内的多次写产生**相同版本**，直接拿来做 CAS 会 ABA 假通过）。

原语 2 / 3（查询型索引、增量持久化 + TTL）落在另一条接缝（读模型与持久化布局）上，由 A2 `add-state-query-index-and-incremental-persistence` 承接——拆分理由见下方「变更粒度取舍」。

## What Changes

- **原语 1（集合粒度追加）**：状态层 SHALL 新增"向集合键逐条追加"的入口，追加只新增元素、不重写既有元素，读取按追加顺序返回；同键并发追加 MUST 不丢更新。既有 `set_state` 的整值替换语义 MUST NOT 改变。
- **原语 4（条件写 / CAS）**：状态层 SHALL 提供带"期望版本"的条件写入口，比较并写入对同一节点 MUST 原子，版本不匹配时 MUST NOT 写入并 MUST 显式给出失败信号。为使版本可用作乐观并发控制，节点版本 MUST 在每次成功写入后严格递增。既有无条件写 MUST NOT 改变契约。
- **修正版本字段缺陷**：`StateNode` 的 `_version` / `version` 双属性合并为单一 `_version`，并改为严格递增——这是 CAS 可用的**前提**，不是附带优化。
- **新增 scope 级写锁**：`StateScope` 增加内部可变锁，使"读-改-写"段在并发下良定义（`ThreadSafeDict` 只保证单次 get / set 原子，不保证 read-modify-write）。
- **无新增配置键**：追加与 CAS 都是**新入口**，不调用则零行为变化；默认行为等价于合入前。
- **不改变**：`set_state` / `get_state` / `remove_state` / 观察者注册与注销 / effect 并发执行与有界等待 / `load_state_machines` 的整表替换恢复语义 / pickle 文件格式。

## 变更粒度取舍（拆 vs 合）

四条原语落在**两条不同接缝**上：一条是**写路径契约**（原语 1 追加 + 原语 4 CAS，改 `StateScope` / `StateNode` / `StateMachineManager`），另一条是**读模型与持久化**（原语 2 查询型索引 + 原语 3 增量持久化 / TTL，改 `StateIndex` 实现与持久化布局）。

**维护者已裁定取「拆成两个变更」**（2026-10-14），理由按项目规约的优先级 **架构一致性 > 业务逻辑连续性 > 开发量最小**：两条接缝本就可分离，按接缝拆成两个各自自洽的变更同时满足架构一致性与业务连续性——A1 单独合入即让"无锁追加 + 无锁 CAS"可用，不依赖持久化布局变更；把最高风险的持久化布局变更（A2）隔离在独立变更内，评审与回滚成本最低。存在"只落 A1 不落 A2"的中间态，该中间态**仍自洽**：追加 + CAS 可用，只是仍整表落盘。

**两变更的共享契约（A2 依赖本变更）**：节点版本的**严格递增语义**与 `get_version()` 读取口由 A1 定义。A2 的读写路径不得另行定义版本语义；A2 的 `compare_and_set` 之外的入口也不得绕过 A1 引入的 scope 级锁。

| 变更 | 覆盖原语 | 接缝 | 估算 |
|---|---|---|---|
| **A1（本变更）** | 1 追加 + 4 CAS | 写路径契约 | ≈ 4 文件 / 250–400 行（含测试） |
| A2 `add-state-query-index-and-incremental-persistence` | 2 查询型索引 + 3 增量持久化 / TTL | 读模型与持久化布局 | ≈ 5–7 文件 / 400–700 行（含测试与文档） |

## Capabilities

### New Capabilities

无。两条原语均为状态层既有行为的扩展，落在既有 `state-machine` 能力内。

### Modified Capabilities

- `state-machine`: 新增两条 Requirement（集合键逐条追加、条件写基于节点版本原子生效）。既有 Requirement（键路径写入语义、观察者注册 / 注销、effect 线程原语、持久化恢复）**不改动**——本变更以 ADDED 形式追加。

## Impact

- **代码**：`zoo_framework/statemachine/state_node.py`（合并版本双属性、严格递增、`append_value`）、`zoo_framework/statemachine/state_scope.py`（scope 级可变锁、`append_state_node`、`compare_and_set`）、`zoo_framework/statemachine/state_machine_manager.py`（`append_state` / `compare_and_set` 入口）。
- **配置**：无新增键。
- **文档**：`docs/`（状态一节）与 `CLAUDE.md` 状态层注释补两条原语；同步更新 `StateMachineManager` / `StateScope` / `StateNode` 的 docstring（中文、Google 风格）。
- **测试**：新增 `tests/test_state_append_cas.py`（追加语义与并发、CAS 成功 / 冲突 / 边界、版本严格递增）。
- **兼容性**：`set_state` 等既有入口的行为与合入前一致；唯一不可逐字节一致之处是**观察者载荷中的版本号取值**（由秒级墙钟时间戳改为严格递增序列，详见 design.md），且当前全仓库无版本号的读取方。
- **依赖**：无新增第三方依赖。
- **后续**：A2 依赖本变更定义的版本语义与 scope 级锁这一共享契约。
- **issue**：#236（本变更回复其中原语 1 与 4 的落地部分）。
