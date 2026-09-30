## 1. 基线收窄与欠债记账

- [ ] 1.1 把「框架自身的进程级共享 MUST 被显式归类」里的全称句 `MUST NOT 依赖隐式的全局单例状态` 收窄为 `MUST NOT 依赖**新引入的**隐式全局单例状态`，并在同一条要求里显式列出已知欠债（`WorkerRegistry._global_registry`、`EventReactorManager.reactor_map`、`EventChannelRegister._channel_map`）；验证：改后**逐句对现状为真**——对每一条欠债载体核对它确实仍存在且仍是隐式全局状态，且无一句把它们表述为"已由容器归类"
- [ ] 1.2 让欠债带**可核对的承接锚点**；验证：`grep -rn "已知欠债" zoo_framework/` 命中三处载体处的标记注释，且每处注释写明它是容器外状态、并指向本要求——**不是悬空注脚**，是仓库内可 grep 的落点（不外链 issue，避免把锚点放在无法自动核对的外部系统里）
- [ ] 1.3 在要求正文里写明**类属性与实例的收编方式不同、量级须分开估**；验证：正文含该限定，防止后续把两者当作同一种改动来估

## 2. 补齐三处缺口

- [ ] 2.1 写入顺序独占取用的契约（块内串行 / 锁按注册项划分且可重入 / 返回真实实例而非代理）；验证：三条各有对应的 `#### Scenario:`，且逐条与实现一致（对照 group 3 既有用例：`test_concurrent_exclusive_blocks_do_not_overlap`、`test_exclusive_is_reentrant_on_one_thread`、`test_exclusive_yields_the_real_instance`）
- [ ] 2.2 写入原型级语义，且**用单一性质 + 派生后果**表述（性质 = 解析结果不被容器缓存；后果 = 每次新建 / 查询为空 / 释放无销毁动作 / 替换仍生效）；验证：要求只声明**一条**性质，其余四处均表述为它的派生后果，而不是并列的独立断言
- [ ] 2.3 写入"线程安全归属声明 MUST 与实例实际行为相符"，含两项可核对要求（依据 MUST 在代码中写明；声明 MUST 有用例固定）；验证：要求含这两项，且不出现"必须如实"这类无法核对的孤立措辞

## 3. 实现侧最小改动（仅注释与用例，无行为改动）

- [ ] 3.1 在三处欠债载体处加"已知欠债"标记注释（`zoo_framework/core/worker_registry.py` 的 `_global_registry`、`zoo_framework/reactor/event_reactor_manager.py` 的 `reactor_map`、`zoo_framework/event/event_channel_register.py` 的 `_channel_map`）；验证：`grep -rn "已知欠债" zoo_framework/` 恰好命中三处，每处写明"容器外状态 + 未收编"
- [ ] 3.2 在两处 `SINGLE_THREAD` 声明处补齐判定依据注释（`EventRegister` 的裸 `list`、`WaiterResultReactor` 的执行期可变字段）；验证：注释指明**具体字段**与"为何不算自保"，而非泛泛说"不安全"
- [ ] 3.3 新增用例固定这两处声明为 `SINGLE_THREAD`；验证：**把任一处的声明改成 `INSTANCE_GUARANTEED` 后用例转红**（即用例具有鉴别力，不是恒真断言）
- [ ] 3.4 确认本组未改动任何运行时行为；验证：`git diff` 只含注释与新增/修改的用例，容器与各管理器的可执行语句零变化

## 4. 验证与归档

- [ ] 4.1 `openspec validate fix-container-spec-baseline --strict` 与 `openspec validate --specs` 均通过；验证：变更与主 spec 基线都通过
- [ ] 4.2 独立实测 `exclusive` 三条语义（**不依赖既有用例**，由并行会话执行作为旁证）；验证：并发进块不重叠、同线程重入不自锁、`type(resolved) is 注册类型`
- [ ] 4.3 全量回归；验证：`pytest -q` 全绿，且用例总数不少于本变更开始前
- [ ] 4.4 确认未夹带范围外改动；验证：`git diff --stat` 限于本变更的 spec / 注释 / 用例；不含依赖变更、不含对容器或管理器行为的改动、不含对容器外载体的收编
- [ ] 4.5 核对收窄后的基线**逐条对现状为真**（这是本变更的核心验收，不是形式检查）；验证：把基线里每一条要求逐句对照当前实现，不存在"字面为假"的句子
