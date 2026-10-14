# Tasks: add-task-layer

> 本变更是 GitHub issue #234 的**第一档：形状 1（`Task` 值对象）+ 形状 2（落到状态机
> 持久化作用域的任务队列）**。维护者已裁定只做前两条；形状 3（运行时容量，已立案 #233）、
> 形状 4（伸缩信号）、形状 5（取消语义加强）**明确不在本次范围**（见 design.md 的 Non-Goals）。

## 0. 已采用的裁定（实现前落定）

| 待定项 | 采用值 | 依据 |
|---|---|---|
| 范围 | **只做形状 1 + 2** | 维护者裁定；1+2 落在"任务层语义"接缝、可单独自洽合入，把调度器变更（#233）隔离 |
| 任务字段名 | `task_id`（非 `id`） | 避免与内建 `id()` 混淆；框架日志词表已用 `task_id`（design D1） |
| 时间戳集合 | `created_at` / `updated_at` / `started_at` / `finished_at` | issue 写"timestamps"（复数），细化为创建 / 更新 / 开始 / 结束 |
| 持久化形态 | 每队列**一个列表节点**（键 `"tasks"`）存任务字典列表 | 顺序天然、单点 CAS、键不触发点分树（design D3）；代价 O(n) 迁移已记录 |
| 原子性原语 | 复用 scope 级锁 + `compare_and_set` 乐观重试；仅新增一把节点引导锁 | 复用 A1 交付的 CAS（design D4） |
| 失败信号形式 | 迁移返回迁移后 `Task` / `None`，取消返回 `bool`；重复身份抛错 | 与 A1 的 CAS"冲突用返回值、调用方错误才抛错"一致 |
| 配置键 | 新增唯一键 `task:queue:scope`（默认 `"zoo.tasks"`），运行期读取 | 默认保持现状（design D6）；不新增容量 / 重试 / 退避键 |
| 取消边界 | 只取消**待跑**任务；MUST NOT 声称中断已开始的执行 | issue 形状 5 的诚实约束（design D5 / spec MUST NOT） |
| 投递幂等 | **不做**；只保证"身份在队列内唯一" | issue #74 未决（design、spec 明写不含幂等承诺） |

以上各项如有异议，维护者可在实现前否决；否决时同步更新本表与 design.md 的 Decisions。

## 1. 前置与基线

- [x] 1.1 全量基线：`F:/Python/zoo/.venv/Scripts/python.exe -m pytest -q`，记录通过数（本树全绿，
      实测 **1258 passed**）；验证：输出留档，作为收口比对基准
- [x] 1.2 复核可复用接缝：确认 `StateScope._mutation_lock` / `compare_and_set`（A1）与
      `StateMachineManager` 的持久化路径存在且语义不变；验证：读 `state_scope.py` /
      `state_machine_manager.py`，结论与 design Context 一致
- [x] 1.3 复核无既有同名能力：`grep -rn "class Task\b" zoo_framework/` 仅命中
      `asyncio.Task` / `_BackgroundTask` 等无关项；验证：无框架级 `Task` 能力，可安全新建

## 2. 任务值对象（形状 1）

- [x] 2.1 `zoo_framework/tasks/task.py`：`TaskStatus(StrEnum)` = pending / running / succeeded /
      failed / cancelled；`Task` dataclass（design D1 的九个字段）+ `to_dict()` / `from_dict()` +
      `Task.new(payload, task_id=None)`；验证：测试覆盖"字段齐全""`new` 自动生成身份""`to_dict`/
      `from_dict` 往返一致"
- [x] 2.2 同上：`Task.from_dict` 对 `status` 用 `TaskStatus(...)` 还原、对未知状态显式失败；
      验证：环绕用例 + "未知状态字面量抛 `ValueError`"
- [x] 2.3 同上：`__post_init__` 把字符串状态归一为 `TaskStatus`；验证：以字符串构造后
      `status is TaskStatus.PENDING`

## 3. 任务队列（形状 2）

- [x] 3.1 `zoo_framework/tasks/task_queue.py`：`TaskQueue(scope=None, manager=None)`——
      作用域经运行期读取配置键（design D6）取默认；内部持 `StateMachineManager`；
      节点引导走双重检查锁（design D4）；验证：默认作用域名断言 + 不产生副作用
- [x] 3.2 同上：`submit(task)`——在 CAS 临界区内拒绝重复身份、否则追加；返回入队任务；
      验证：测试覆盖提交后按身份读回、重复身份显式报错且队列不增
- [x] 3.3 同上：`get(task_id) -> Task | None` 与 `tasks(status=None) -> list[Task]`（按提交顺序）；
      验证：测试覆盖按身份读回、按状态过滤、不存在返回 None、顺序稳定
- [x] 3.4 同上：`claim(task_id) -> Task | None`（pending→running，attempts+1）与
      `claim_next() -> Task | None`（原子认领最老的待跑任务）；验证：测试覆盖认领成功 /
      对非待跑认领返回 None / attempts 递增
- [x] 3.5 同上：`complete(task_id, result=None)`、`fail(task_id, error)`、`requeue(task_id)`；
      验证：测试覆盖完成记录结果与结束时间、失败记录错误、requeue 把 running/failed 改回
      pending 且 attempts 不再增
- [x] 3.6 同上：`cancel(task_id) -> bool`——仅 pending 生效；对 running / 终态返回 False；
      验证：测试覆盖取消后不可认领、取消 running 不生效
- [x] 3.7 同上：`_mutate` 乐观重试（CAS 失败重试，耗尽抛错），只在版本匹配时提交；
      验证：并发用例（3.9）稳定通过

## 4. 持久化与重启（形状 2 的核心承诺）

- [x] 4.1 队列数据落在 `StateMachineManager` 的作用域内：提交即经状态机写路径（天然可落盘）；
      验证：测试断言"提交后 `StateMachineManager().get_state(scope, 'tasks')` 可见该任务字典"
- [x] 4.2 重启不丢待跑任务：用同一落盘内容（`pickle` 往返 / `load_state_machines`）重建队列后，
      待跑任务的身份 / 载荷 / 状态 / 尝试次数一致，提交顺序保持；验证：测试覆盖"落盘→重建→读回一致"
      与"顺序 A/B/C 保持"
- [x] 4.3 重启后处于**执行中**的任务不静默重跑：恢复后仍为 running、不被自动改回 pending；
      显式 `requeue` 后才回 pending；验证：测试覆盖"重启后 running 保持可查""不自动重跑"
      "显式 requeue 后回 pending"

## 5. 并发正确性

- [x] 5.1 并发认领同一任务恰好一个成功、attempts 为 1；验证：`threading.Barrier` 双线程用例
      稳定通过（重跑多次）
- [x] 5.2 并发提交不同身份不丢更新；验证：多线程提交数 == 读回任务数
- [x] 5.3 认领与提交混跑不丢更新（提交数 + 认领数自洽）；验证：并发用例通过

## 6. 配置键与默认零行为变化

- [x] 6.1 `zoo_framework/params/task_params.py`：`TaskParams.QUEUE_SCOPE =
      param(value="task:queue:scope", default="zoo.tasks")`；`params/__init__.py` 导出；
      验证：默认值断言
- [x] 6.2 运行期读取：`TaskQueue.__init__` 内**惰性导入** `TaskParams`（不得置于模块导入期）；
      验证：测试打桩配置后新建队列取到配置值
- [x] 6.3 不使用任务层时既有行为不变；验证：用例断言"不提交任务即不产生任务作用域 /
      既有 set_state / 调度不受影响"

## 7. 文档与收口

- [x] 7.1 文档：`docs/`（状态持久化 + 配置参考）补任务层说明与新键；`docs/api/state.md`
      补队列 API 的 mkdocstrings 指令；`docs/guides/config-reference.md` 补 `task:queue:scope`；
      验证：`pytest tests/test_doc_consistency.py -q` 不因本变更新增失败
- [x] 7.2 文档：教程或指南补一段"任务队列 + 重启不丢"的最小用法（如有教程页）
- [x] 7.3 全量门禁：`ruff check zoo_framework` / `ruff check tests` / `ruff check example` 三条
      零错误；`mypy zoo_framework` 零错误；`python -m pytest -q`（与 1.1 基线 1258 对比，
      记录增量、确认无新增失败）；`openspec validate add-task-layer --strict` 通过；
      验证：五条命令输出留档
- [x] 7.4 断言有效性：对关键用例注入违规实现确认变红，按备份逐字节还原；验证：
      `git status --porcelain` 只含本变更文件、`git grep VIOLATION` 无残留。
      **执行中发现并修复**：并发用例（5.1 / 5.2 / 5.3）原仅靠 `threading.Barrier` 起跑，
      默认 GIL 切换间隔下临界区太短，注入"盲写（不走 CAS）"的丢失更新实现时**照样全绿**
      ——断言没有牙齿。改为在 `StateNode.get_value` 上装一枚**取值后**会合的读闸门
      （`_install_read_gate`：先取值再等屏障，保证所有参与者都先拿到同一旧快照），使竞态
      确定性暴露。修复后注入验证：盲写实现令 3 条并发用例全红（认领 2 个赢家 / 提交 5≠30 /
      混跑 5≠20）；另注入"取消对执行中任务也生效"令取消诚实性用例变红。两次注入均按备份
      逐字节还原（`task_queue.py` md5 复原为 `0b126d11…`，`grep VIOLATION` 无残留）。

## 8. 故意留空（不在本变更）

- [ ] 8.1 **形状 3 运行时容量**（池 `resize`、`add_worker` / `submit` 与启动期同一套准入、修
      #233）——**故意留空**：已单独立案 #233，属独立接缝，不做即不越界
- [ ] 8.2 **形状 4 伸缩信号**（队列深度 / 在飞数 / 失败退避驱动的策略、复用
      `WorkerDelayManager`）——**故意留空**：本变更只提供谓词式状态查询，不提供任何自适应 / 退避
- [ ] 8.3 **形状 5 取消语义加强**（协作式取消、把取消传进执行体）——**故意留空**：只做"取消
      尚未启动的"，诚实约束已落成 spec 的 MUST NOT 条文
- [ ] 8.4 **投递幂等收口**——**故意留空**：issue #74 未决，本变更只保证身份唯一，不承诺投递语义
