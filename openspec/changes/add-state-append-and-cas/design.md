# Design: add-state-append-and-cas

## Context

见 proposal.md（Why）与 specs/state-machine/spec.md（Requirements）。实现前必须知道的现状与约束：

- `StateNode` 的版本有**双属性缺陷**：`__init__` 写 `self._version`，而 `set_value` → `_update_version()` 写的是 `self.version`（另一个属性）。`_version` 自构造后从不更新，`version` 在首次 `set_value` 前**不存在**（读取会 `AttributeError`）。全仓库**没有任何版本读取方**。
- 版本取值是 `int(time.time())`（秒级），同一秒内的多次写会产生**相同版本**——直接拿来做 CAS 会 ABA 假通过。这是本变更必须先修缺陷、再谈 CAS 的原因。
- `ThreadSafeDict` 只保证单次 get / set 原子，**不保证 read-modify-write**。所以"追加"与"CAS"都不能靠"先读后写"两步实现。
- `StateScope` 当前**没有**任何变更级别的锁；`StateMachineManager` 也没有。
- `set_state` 的整值替换语义、观察者注册 / 注销、effect 线程池并发 + 5s 有界等待：均已由既有 spec 冻结，本变更不得改动。
- 本变更是拆分的 **A1**（写路径契约）。A2 `add-state-query-index-and-incremental-persistence` 依赖本变更定义的**版本严格递增语义**与 **scope 级锁**这一共享契约。

## Goals / Non-Goals

**Goals:**

- 两条原语的**最小可用**契约，落点在既有接缝（`StateNode` / `StateScope` / `StateMachineManager`），不新造抽象层。
- 版本成为**可用的乐观并发控制**前提（严格递增、可读、CAS 原子）。
- **未使用新入口时既有行为不变**（无需任何配置开关——新能力只走新入口）。
- 每条契约都有对应场景（见 spec delta），可测可验。

**Non-Goals:**

- 不做"记忆层"——上下文记忆 / 规则 / top-k 注入 / 语义检索属消费方（zoo-code-agent#37 / #41），内核只给原语。
- 不做查询型索引与增量持久化 / TTL——那是 A2 的范围。
- 不做跨进程一致性与分布式 CAS（单进程内线程安全即达标）。
- 不改变 `set_state` / effect / 观察者触发的既有契约。

## Decisions

### D1：追加走新增入口，语义落在"序列节点"

新增 `StateMachineManager.append_state(scope, key, item)` → `StateScope.append_state_node(key, item)` → `StateNode.append_value(item)`。类型判定以 **`isinstance(node.get_value(), list)`** 为准，**不依赖 `node.get_type()`**——`StateNode.__init__` 不调用 `StateNodeType.get_type_by_value`（`register_node(key, [..])` 建出的节点 `_type` 仍是 `string`），按 `_type` 判定会误判。

- 节点不存在 → 以 `[item]` 建节点后返回；
- 节点值为 `list` → **就地 append**，随后仅更新版本并触发 effect（不重建既有元素、不重排）；
- 节点值为 `dict`（branch / 子树）或其它非 list 值 → 抛 `TypeError`，不覆盖原值（dict 的"追加"语义与子树构造语汇冲突，明确拒绝而非猜测）；
- `tuple` 不被 `StateNodeType` 识别为 array，**不支持**（保持最小面）。

替代方案：用某种"集合值包装类型"经既有 `set_state` 传参——被否，因为会污染对 `value` 透明的既有契约（`set_state` 的整值替换语义是冻结条款）。

### D2：版本语义修正为"严格递增"，并合并双属性

`StateNode` 统一为**单一** `_version`，公开读取口 `get_version()`；`set_value` / `append_value` 内以 `self._version = max(self._version + 1, int(time.time()))` 更新，**先更新版本、再触发 effect**，使观察者载荷中的版本是新版本。

- 为什么用 `max(prev + 1, time())` 而不是纯计数器：保留"版本数量级≈墙钟秒"的既有观感，把对观察者载荷的**取值差异压到最小**——仅在"同一秒内多次写"时才与旧值不同；纯计数器会让所有版本值立刻变成小整数，差异面更大。
- 为什么必须严格递增：秒级时间戳在同一秒重复会导致 CAS ABA 假通过（见 Context）。
- **兼容影响**：观察者载荷 `version` 的取值定义从"墙钟秒"变为"严格递增序列"，这是本变更**唯一**不逐字节一致之处；已核实全仓库无版本读取方（`grep` 无命中），风险面只在框架外部消费者。
- 此语义是 A2 的**共享契约**：A2 不得另行定义版本语义。

### D3：CAS 走新增入口，返回布尔，原子性由 scope 级锁保证

新增 `StateMachineManager.compare_and_set(scope, key, expected_version, value) -> bool`。语义：在**同一临界区**内读取节点当前版本、与 `expected_version` 严格相等比较、相等才写并递增版本；返回 `True`（已写） / `False`（未写）。不抛异常表示冲突——冲突是**预期结果**而非错误，返回值便于调用方重试；参数 / 状态本身非法（如节点不存在而 `expected_version` 非 None）才抛错。

- 原子性载体：新增 `StateScope._mutation_lock = threading.RLock()`，`set_state_node` / `append_state_node` / `compare_and_set` 的"读-改-写"段统一持锁；无条件 `set_state` 也持同一把锁，使"版本递增"在并发下良定义。锁粒度为 **scope 级**（一个 scope 的变更串行化），不动全局锁。
- 替代方案一：per-node 锁——更细，但节点生命周期短、建锁 / 换节点要额外记账，收益不抵复杂度。替代方案二：不引入锁、靠"版本检查 + 原子 set"两步——存在窗口，不满足 spec 的原子性场景。
- 此锁是 A2 的**共享契约**：A2 新增的写路径（若有）也必须持同一把锁。
- **CAS 失败信号取值**：采用设计推荐的**返回 `bool`**（而非抛专用异常）。理由见 tasks.md 的「已采用的裁定」；若维护者要求"当前版本一并返回以便重试"，可在 `bool` 之外追加一个返回当前版本的入口，属追加而非改契约。

### D4：向后兼容判定（未使用新入口时是否逐字节一致）

| 面 | 判定 |
|---|---|
| `set_state` / `get_state` / `remove_state` / `observe_state` / `unobserve_state` | **逐字节一致**：入口契约与返回不变；仅内部多持一把 scope 锁（无可观测语义变化） |
| `load_state_machines` 恢复语义（整表替换） | **一致**：本变更不动持久化路径 |
| pickle 文件内容 | **一致**：本变更不动持久化格式 |
| 观察者触发次数 / 载荷 `value` | **一致** |
| 观察者载荷 `version` 取值 | **不逐字节一致**（唯一差异点，见 D2）：由秒级时间戳变为严格递增序列；全仓库无读取方 |

## Risks / Trade-offs

- [D2 的版本取值变化触及观察者载荷] → 已核实全仓库无读取方；`max(prev+1, time())` 把差异压缩到"同一秒多次写"；如维护者要求**完全**零差异，可退化为"仅在 CAS 被使用时才启用严格递增"（代价：无条件写与 CAS 混用时仍可能 ABA）。
- [D3 的 scope 级锁带来写路径开销] → 锁只在单 scope 内串行，跨 scope 不互斥；相比消费者自己加锁（现状）净收益为正；如需进一步优化可后置为 per-node 锁。
- [追加的类型判定依赖 `isinstance` 而非节点声明类型] → 这是刻意规避 `get_type()` 的已知误判（见 D1），以 `isinstance` 为唯一判据并在 docstring 明示；`tuple` / `dict` 明确拒绝而非猜测。
- [合并版本双属性可能影响既有反序列化产物] → `StateNode` 的 pickle 载荷含 `_version` 与 `version` 两个键，合并后旧存档的 `version` 变冗余字段。设计取"读取时兼容、写入时只写 `_version`"（`__setstate__` 兜底），并把该点在任务中用测试固定。

## Migration Plan

- **无数据 / 配置迁移**。不使用新入口的调用方，行为逐字节不变。
- 回滚策略：本变更为新增入口 + 版本语义修正，回滚即还原代码；不涉及持久化格式变更，无残留状态（唯一注意点：回滚后旧存档中已按新语义递增的版本值仍是合法整数）。
- 下游衔接：A2 在本变更合入后即可依赖版本语义与 scope 级锁开工。
