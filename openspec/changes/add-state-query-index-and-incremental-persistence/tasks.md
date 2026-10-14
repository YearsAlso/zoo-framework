# Tasks: add-state-query-index-and-incremental-persistence

> 本变更是 #236 拆分后的 **A2**（读模型与持久化：原语 2 查询型索引 + 原语 3 增量持久化 / TTL）。
> A1 `add-state-append-and-cas` 承接原语 1 / 4，**必须先落地**（见 proposal.md「依赖」）。

## 0. 已采用的裁定（维护者 2026-10-14）

| 原 Open Question | 采用值 | 依据 |
|---|---|---|
| 是否拆变更 | **拆**（A1 = 原语 1+4，A2 = 原语 2+3） | 维护者裁定；把最高风险的持久化布局变更隔离在独立变更内 |
| 增量持久化布局 | **每作用域文件**（D2），`picklePath` 在开关下解释为目录 | "单文件 + 脏门控"不满足 spec 的「未修改的作用域 MUST NOT 被重写」 |
| 增量键语义 | `picklePath` 随开关切换语义（备选：另立 `stateMachine:incrementalDir`） | 少一个键；**可在实现前否决** |
| 查询面 | **谓词函数 + 关键词子串**（不做排序 / 相关度 / 语义） | issue 边界：检索策略留在上层 / 插件 |
| TTL 基准 | **最后写入**（非 LRU） | 读路径零改动，改动面最小 |

以上各项如有异议，维护者可在实现前否决；否决时同步更新本表与 design.md 的 Decisions 与 Open Questions。

## 1. 前置与基线

- [ ] 1.1 确认 A1 已合入本树：`git log --oneline -5` 含 A1 的实现提交；`pytest tests/test_state_append_cas.py -q` 全绿
- [ ] 1.2 记录基线：`pytest tests/test_state_machine.py tests/test_statemachine.py
      tests/test_state_restore.py -q` 存下通过数；验证：基线命令全绿且输出留档
- [ ] 1.3 全量基线：`python -m pytest -q`，记录通过数（本树无未跟踪的 `docs/docs/` 与
      `node_modules/`，预期全绿）；验证：输出留档，作为收口比对基准

## 2. 查询型索引默认实现（原语 2）

- [ ] 2.1 `zoo_framework/statemachine/state_index_factory.py`：新增查询型 `StateIndex` 实现
      （按谓词函数与关键词子串过滤节点值），**不**修改 `StateIndex` ABC 的抽象方法集；
      验证：测试覆盖"返回恰好匹配的节点""空索引 / 无匹配返回空结果"
- [ ] 2.2 同上：把该实现注册进 `StateIndexFactory._index_types`（名 `"queryable"`）；
      验证：`StateIndexFactory.get_available_types()` 含新名，`create_index("queryable")`
      返回该实现的实例
- [ ] 2.3 `zoo_framework/params/state_machine_params.py`：新增
      `STATE_INDEX_TYPE = param(value="stateMachine:indexType", default="dict")`；
      `StateMachineManager.create_scope` 于**运行期**读取该键构造 `StateScope(index_type=...)`
      （不得置于模块导入期）；验证：测试"未配置时用默认 dict 索引"（向后兼容）与
      "配置未知索引名抛 ValueError"
- [ ] 2.4 并发：验证持续写入下执行查询不崩溃；验证：并发查询测试通过（重跑多次）
- [ ] 2.5 跨平台：该实现为纯 Python 数据结构，三平台行为一致；验证：CI 三平台矩阵对应作业全绿

## 3. 增量持久化与 TTL 淘汰（原语 3）

- [ ] 3.1 `zoo_framework/statemachine/state_machine_manager.py`：新增脏作用域记账——每次成功写入
      （`set_state` / `append_state` / `compare_and_set`，含 A1 的入口）在 `_mutation_lock` 临界区内
      标记该 scope 脏；验证：测试"写入 scope A 后 A 为脏、未写的 B 不为脏"
- [ ] 3.2 `zoo_framework/statemachine/state_scope.py`：新增 `last_modified`（墙钟 `time.time()`），
      随 scope pickle，并补 `__setstate__` 兼容旧存档缺该字段的情形；
      验证：测试写入后时间戳被刷新 + 反序列化旧载荷不抛错
- [ ] 3.3 落盘路径（D2 每作用域文件）：`zoo_framework/workers/state_machine_work.py` 按
      `stateMachine:incrementalSave` 读取脏集合，仅写脏作用域的文件 + 原子替换 manifest；
      **未启用时保持整表落盘**；验证：测试"未修改的作用域不被重写""启用后在新进程语境读回
      与整表落盘等价""未启用时仍整表落盘"
- [ ] 3.4 迁移路径（D2）：增量模式启用时若 `picklePath` 指向既有整表文件，先读入、以目录布局
      写出、原文件改名 `<原名>.migrated.bak`；验证：测试覆盖"旧整表文件 → 目录布局，
      数据无丢失且原文件留档"
- [ ] 3.5 `zoo_framework/params/state_machine_params.py`：新增 `INCREMENTAL_SAVE` /
      `SCOPE_TTL_SECONDS` 配置键（默认 `false` / `0`）；验证：默认值测试 + 参数解析测试
- [ ] 3.6 `StateMachineManager.evict_expired_scopes(ttl)`：按 `last_modified` 与墙钟淘汰过期 scope，
      幂等，并在增量模式下清理其持久化文件；`StateMachineWorker` 每拍调用；验证：测试"过期被移除
      且查询返回空""重复淘汰不抛错""未配置 TTL 时不淘汰"
- [ ] 3.7 失败语义：落盘失败仍抛显式 `PersistenceError`（复用既有 `PicklePersistenceStrategy`
      的原子写，不因增量改造而退化）；验证：目标目录不可写时测试抛出 `PersistenceError`
- [ ] 3.8 跨平台：在 Windows / Linux / macOS 验证原子替换与目录布局落盘一致（本地至少 Windows；
      其余由 CI 三平台矩阵覆盖）；验证：`pytest` 在 CI 三平台对应作业全绿

## 4. 文档与收口

- [ ] 4.1 文档：`docs/`（状态一节）与 `CLAUDE.md` 状态层注释补两条原语、三个配置键与默认值、
      TTL 时间基准（墙钟、最后写入）、查询型索引的朴素定位与**弱一致**语义、增量模式的
      `picklePath` 语义与迁移步骤；同步更新相关类 docstring（中文、Google 风格）；
      验证：`pytest tests/test_doc_consistency.py -q` 不因本变更新增失败
- [ ] 4.2 全量门禁：`ruff check zoo_framework` / `ruff format --check zoo_framework` /
      `mypy zoo_framework` 零错误 / `python -m pytest -q`（与 1.3 基线对比，确认无新增失败）/
      `openspec validate add-state-query-index-and-incremental-persistence --strict` 通过；
      验证：五条命令输出留档
- [ ] 4.3 回调：在 issue #236 下评论说明 A2 的落地范围（原语 2 与 3）、三个配置键的默认值不变性、
      TTL 基准与弱一致语义；验证：issue 评论已张贴
