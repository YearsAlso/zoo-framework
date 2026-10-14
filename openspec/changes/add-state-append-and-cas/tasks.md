# Tasks: add-state-append-and-cas

> 本变更是 #236 拆分后的 **A1**（写路径契约：原语 1 追加 + 原语 4 CAS）。
> A2 `add-state-query-index-and-incremental-persistence` 承接原语 2 / 3，**依赖本变更**定义的
> 版本严格递增语义与 scope 级锁。

## 0. 已采用的裁定（维护者 2026-10-14）

| 原 Open Question | 采用值 | 依据 |
|---|---|---|
| 是否拆变更 | **拆**（A1 = 原语 1+4，A2 = 原语 2+3） | 维护者裁定；两条接缝本可分离，A1 单独合入即解阻塞 |
| CAS 失败信号形式 | **返回 `bool`**（`True` 已写 / `False` 未写）；参数或状态非法才抛错 | 冲突是预期结果而非错误；返回值便于调用方重试 |
| 追加的集合面 | **只支持 `list`**；`dict`（子树）与 `tuple` 明确拒绝 | `dict` 的"追加"与子树构造语汇冲突；`tuple` 不被 `StateNodeType` 识别，保持最小面 |
| 版本值兼容性 | **接受**观察者载荷 `version` 由秒级时间戳变为严格递增序列 | 全仓库无版本读取方（1.3 复核）；`max(prev+1, time())` 已把差异压到最小 |

以上各项如有异议，维护者可在实现前否决；否决时同步更新本表与 design.md 的 Decisions。

## 1. 前置与基线

- [x] 1.1 记录基线：在改动前运行 `pytest tests/test_state_machine.py tests/test_statemachine.py
      tests/test_state_restore.py -q` 并存下通过数；验证：基线命令全绿且输出留档
- [x] 1.2 全量基线：`python -m pytest -q`，记录通过数（本树无未跟踪的 `docs/docs/` 与
      `node_modules/`，预期全绿）；验证：输出留档，作为收口比对基准
- [x] 1.3 确认无版本读取方：`grep -rn "get_version\|\.version" zoo_framework/ tests/ --include=*.py`，
      记录结论；验证：结果与 design.md Context 描述一致（无既有读取方）

## 2. 版本语义与节点写路径（原语 4 的地基）

- [x] 2.1 `zoo_framework/statemachine/state_node.py`：合并 `_version` / `version` 双属性为单一
      `_version`，新增 `get_version()`；`set_value` 内以 `max(self._version + 1, int(time.time()))`
      更新且**先更新版本再触发 effect**；验证：新增测试断言连续两次写入后版本严格递增、
      且观察者载荷中的版本等于写入后的版本
- [x] 2.2 同上：为旧存档补 `__setstate__` 兜底（旧载荷同时含 `version` 与 `_version` 时
      归一为单一 `_version`）；验证：用改造前生成的 pickle 载荷反序列化后 `get_version()` 可读且不抛错
- [x] 2.3 同上：新增 `append_value(item)`，仅接受 `isinstance(get_value(), list)` 的节点
      （就地 append、不重建既有元素、更新版本并触发 effect），非 list 抛 `TypeError` 且不覆盖原值；
      验证：测试覆盖"追加后元素与顺序不变""对 int 值键追加抛 TypeError 且原值不变"
- [x] 2.4 `zoo_framework/statemachine/state_scope.py`：新增 `_mutation_lock = threading.RLock()`，
      使 `set_state_node` / 新增的 `append_state_node` / 新增的 `compare_and_set` 的读-改-写段
      持同一把锁；验证：并发测试（多线程追加不丢元素、多线程相同期望版本 CAS 仅一成功）稳定通过

## 3. 追加式集合（原语 1）

- [x] 3.1 `zoo_framework/statemachine/state_scope.py`：新增 `append_state_node(key, item)`——键不存在以
      `[item]` 建节点，存在则委托 `StateNode.append_value`；验证：测试覆盖"对不存在键追加自动创建"
      "逐条追加 A/B/C 后按序读回""对 dict 值键追加抛 TypeError"
- [x] 3.2 `zoo_framework/statemachine/state_machine_manager.py`：新增 `append_state(scope, key, item)`
      （按需建 scope 后转发）；验证：manager 层测试覆盖追加与按序读回
- [x] 3.3 回归：确认既有 `set_state` 整值替换语义未被改动；验证：
      `pytest tests/test_state_machine.py tests/test_statemachine.py` 全绿，
      且新增测试断言"整值写入仍整体替换集合键"

## 4. 条件写 CAS（原语 4）

- [x] 4.1 `zoo_framework/statemachine/state_scope.py`：新增
      `compare_and_set(key, expected_version, value) -> bool`，在临界区内比较严格相等、
      相等才写并递增版本，返回是否已写；节点不存在 / 无可比版本时抛错；验证：测试覆盖成功、
      过期版本不写、节点不存在报错
- [x] 4.2 `zoo_framework/statemachine/state_machine_manager.py`：新增
      `compare_and_set(scope, key, expected_version, value) -> bool`；验证：manager 层测试覆盖
      成功 / 冲突 / 冲突后原值不变
- [x] 4.3 并发正确性：验证相同期望版本的并发 CAS 恰好一个成功；验证无条件 `set_state` 与 CAS
      混用下版本仍严格递增；验证：并发测试稳定通过（重跑多次）

## 5. 文档与收口

- [x] 5.1 文档：`docs/`（状态一节）与 `CLAUDE.md` 状态层注释补两条原语与使用方式；
      同步更新 `StateMachineManager` / `StateScope` / `StateNode` 的 docstring（中文、Google 风格）；
      验证：`pytest tests/test_doc_consistency.py -q` 不因本变更新增失败
- [x] 5.2 全量门禁：`ruff check zoo_framework` / `ruff format --check zoo_framework` /
      `mypy zoo_framework` 零错误 / `python -m pytest -q`（与 1.2 基线对比，确认无新增失败）/
      `openspec validate add-state-append-and-cas --strict` 通过；验证：五条命令输出留档
- [ ] 5.3 回调：在 issue #236 下评论说明 A1 的落地范围（原语 1 与 4）、默认行为不变性、
      以及 A2 承接原语 2 / 3 的分工；验证：issue 评论已张贴
      （GitHub 回调属远程操作，交由主会话执行）
