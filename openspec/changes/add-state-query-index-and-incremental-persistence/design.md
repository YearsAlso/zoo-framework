# Design: add-state-query-index-and-incremental-persistence

## Context

见 proposal.md（Why）与 specs/state-machine/spec.md（Requirements）。实现前必须知道的现状与约束：

- `StateScope.__init__(index_type="dict")` 已通过 `StateIndexFactory.create_index` 建索引，但 `StateMachineManager.create_scope` 恒以默认值构造 `StateScope()`——**没有任何配置键能选索引类型**。
- `StateIndex` ABC 的接口是 `get/set/remove/has/get_all/find_by_prefix`；内置实现 `ThreadSafeDictIndex`（线性前缀扫描）与 `HierarchicalIndex`。`StateIndexFactory._index_types` 是类级注册表，且已在 `core/process_state.py`（第 304 行起）登记为进程级共享载体（被 `watch`）；新增内置类型是**追加**，不破坏该登记。
- 持久化路径有**两条并存**：`StateMachineWorker._save_state_machines`（当前实际使用，整表 `deepcopy + pickle`，每拍重写）与 `core/persistence_scheduler.py`（有 `mark_dirty` / `is_dirty`，但 state 侧未接线）。两者都不做脏跟踪、不淘汰。
- 配置键现只有 `stateMachine:picklePath`（文件）与 `stateMachine:delay`（秒）。`StateMachineParams` 在 `@params` 下于**首次导入时**解析，导入早于 `Master` 读配置会冻结默认值——新增键的读取必须发生在配置已读之后（在 scope / Worker 运行时读取，而非模块导入期）。
- 落盘已有原子写 + 校验 + 滚动备份的既有实现（`core/persistence_scheduler.py` 的 `PicklePersistenceStrategy`），失败经 `PersistenceError` 显式化。增量改造必须**复用**该失败语义，不得退化为"只记日志"。
- 本变更是拆分的 **A2**，**依赖 A1**（`add-state-append-and-cas`）：脏标记要挂在 A1 引入的 `StateScope._mutation_lock` 临界区内，且不得另行定义节点版本语义。

## Goals / Non-Goals

**Goals:**

- 两条原语的**最小可用**契约，落点在既有接缝（`StateIndexFactory` / `StateMachineManager` / `StateMachineWorker` / 持久化策略），不新造抽象层。
- **未启用新能力时既有行为不变**：所有新增能力由默认关闭 / 默认取现状值的新配置键控制。
- 每条契约都有对应场景（见 spec delta），可测可验。

**Non-Goals:**

- 不做"记忆层"——上下文记忆 / 规则 / top-k 注入属消费方（zoo-code-agent#37 / #41）。
- 不内置语义 / 向量检索（issue 边界：检索策略留在上层 / 插件）。
- 不为 `StateIndex` ABC 增加抽象方法（否则第三方已注册索引会因未实现新抽象方法而实例化失败）。
- 不做跨进程一致性与分布式状态（单进程内线程安全即达标）。
- 不改变 A1 已定义的版本语义与写路径锁。

## Decisions

### D1：查询型索引 = 朴素谓词 / 关键词索引，经配置键选取

新增 `StateIndex` 实现（暂名 `QueryableIndex`，"查询"能力 = 在 `get_all()` 之上按**谓词函数**或**关键词包含**过滤节点值），注册进 `StateIndexFactory._index_types`（名如 `"queryable"`）。选取经新配置键 `stateMachine:indexType`，默认 `"dict"`（现状）；未知类型名沿用工厂既有 `ValueError`。

- 索引类型在 `StateMachineManager.create_scope` 构造 `StateScope(index_type=...)` 时从 `StateMachineParams.STATE_INDEX_TYPE` **运行期**读取（不置于模块导入期，避免冻结默认值）。
- **不**为 `StateIndex` ABC 增加抽象方法（见 Non-Goals）；查询作为该实现的**具体方法**暴露，不进入 ABC 契约。
- 关键词匹配为大小写敏感的朴素子串 / 等值匹配；排序、相关度、语义均**不做**（issue 边界）。查询结果弱一致（并发写入下可能看到进行中的状态），在 docstring 明示。
- 替代方案：把查询做成 `StateScope` 上的独立方法而非新索引类型——被否，因为会绕过"可插拔索引"这一既有接缝，且无法被配置键选中。

### D2：增量持久化 = 脏作用域记账 + 每作用域文件

脏记账落在 `StateMachineManager`：每次成功写入（`set_state` / `append_state` / `compare_and_set`）在 `_mutation_lock` 临界区内标记该 scope 为脏（`_dirty_scopes: set[str]`）；`StateMachineWorker` 每拍读取并按配置决定落盘方式。

**采用每作用域文件布局**（而非"整表单文件 + 脏门控"）：启用增量模式时，`stateMachine:picklePath` 解释为**目录**，内含一个 manifest（scope 名 → 文件名 / 版本）与每作用域一个文件；落盘只写脏 scope 的文件（逐文件 `os.replace` 原子替换），并短窗口更新 manifest。

- 为什么必须每作用域文件："整表单文件 + 脏门控"只解决"无脏时跳过落盘"，**不满足** spec 的「未修改的作用域 MUST NOT 被重写」——只要有一个脏 scope，B 也会被重写进同一个文件。故该备选被否。
- 原子性：manifest 采用"先写 scope 文件、后原子替换 manifest"，启动恢复以 manifest 为准、孤儿文件忽略。
- 迁移：启动时若增量模式已启用、而 `picklePath` 指向的是**既有的整表文件**，则先按旧格式读入，再以目录布局重新写出，并把原文件重命名为 `<原名>.migrated.bak`（不删数据、不静默误读）。
- 失败语义：复用既有 `PicklePersistenceStrategy` 的原子写，失败抛 `PersistenceError`，不退化。

### D3：TTL 淘汰 = scope 时间戳 + 每拍扫描，墙钟基准

`StateScope` 增加 `last_modified`（墙钟 `time.time()`，随 scope 一起 pickle，**重启后仍可判**）。新配置键 `stateMachine:scopeTtlSeconds`，默认 `0` = **不淘汰**（现状）。`StateMachineWorker` 每拍调用 `StateMachineManager.evict_expired_scopes(ttl)`：过期即从 `_state_scope_map` 移除，并（增量模式下）删除其持久化文件。

- 基准选**墙钟**而非单调钟：TTL 需跨重启成立，`time.monotonic` 进程内才有意义。
- 语义取"**最后写入**"而非"最后访问"：读路径不加时间戳，改动面最小；若将来要 LRU 语义，那是独立变更。
- 幂等：对已移除作用域再次淘汰为 no-op（`pop(key, None)`）。

### D4：新增配置键与默认值（全部保持现状）

| 键 | 默认 | 现状对应 |
|---|---|---|
| `stateMachine:indexType` | `"dict"` | 现值即默认索引类型 |
| `stateMachine:incrementalSave` | `false` | 现值即整表落盘 |
| `stateMachine:scopeTtlSeconds` | `0`（关闭） | 现值即永不淘汰 |

三条键的读取均发生在**运行期**（scope 构造 / Worker 每拍），不置于模块导入期——见 Context 的 `@params` 冻结默认值陷阱。

### D5：向后兼容判定（未启用新能力时是否逐字节一致）

| 面 | 判定 |
|---|---|
| `set_state` / `get_state` / `remove_state` / 观察者契约 | **逐字节一致** |
| `load_state_machines` 恢复语义（整表替换） | **一致**：未启用增量模式时落盘 / 读回形态与合入前相同 |
| pickle 文件内容 | **一致**：未启用增量 / TTL 时仍为 `ThreadSafeDict[str, StateScope]` 整表 |
| `StateIndex` 既有接口与 `find_by_prefix` | **一致**：不新增 ABC 抽象方法，不删既有实现 |
| `StateIndexFactory.get_available_types()` | **追加**一个名字（非破坏；该字典已在 `core/process_state.py` 登记为进程级载体，新增键不影响其 `watch` 语义） |
| `StateScope` 新增 `last_modified` 字段 | **字段追加**：旧存档反序列化时缺该字段，按 0 / 首次写入时补（`__setstate__` 兜底），不改变既有字段 |

## Risks / Trade-offs

- [D2 让 `picklePath` 在开关下语义从"文件"变"目录"] → 开关默认关闭，未启用时纯文件；目录布局的 manifest 与作用域文件存在**短窗口不一致** → manifest 采用"先写 scope 文件、后原子替换 manifest"，启动恢复以 manifest 为准、孤儿文件忽略。**此点维护者可否决**（备选：另立 `stateMachine:incrementalDir` 键，避免同一键两种语义）。
- [TTL 用墙钟，系统时间回拨 / 跨机时钟漂移会使过期判定异常] → 文档明示基准；默认关闭，启用方自担。
- [查询型索引对大树做全量过滤，性能不如专用索引] → 定位是"朴素默认实现"，docstring 明示；重查询场景由插件替换索引类型。
- [新增配置键若被误置为未知索引名] → 工厂沿用既有 `ValueError` 显式失败，不静默回退。
- [增量模式首次启动撞上既有整表文件] → D2 的迁移路径（读入 → 目录落盘 → 原文件改名留档），并用测试固定。

## Migration Plan

1. 合入即生效的仅是"新增索引实现 + 新增配置键（默认取现状值）"，默认行为等价（D5）。
2. 消费方按需在 `config.json` 置 `stateMachine:indexType` / `stateMachine:incrementalSave` / `stateMachine:scopeTtlSeconds`。
3. 启用增量模式前，`picklePath` 指向的既有整表文件**不可直接当目录用** → 由 D2 的启动迁移路径处理（读入 → 目录布局 → 原文件改名 `<原名>.migrated.bak`），文档同步说明。
4. 回滚 = revert 变更提交串；已写出的目录布局在回滚后需还原为整表文件（回滚前先导出），文档说明。

## Open Questions

以下不影响 spec 的条款措辞（条款只写能力行为，不写布局 / 参数形式），但影响落地形态：

1. **增量持久化键语义**（D2）：`picklePath` 随开关在"文件"与"目录"间切换语义，还是另立 `stateMachine:incrementalDir`。本设计按前者实现，**维护者可否决**。
2. **查询面取舍**：谓词函数 / 关键词子串 / 等值匹配，三者取哪几个作为"朴素默认实现"的对外面（本设计取**谓词 + 关键词子串**两项）。**维护者可否决**。
3. **TTL 基准**：最后写入（本设计取此项，读路径零改动）vs 最后访问（LRU，需读路径也写时间戳）。**维护者可否决**。
