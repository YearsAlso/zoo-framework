# Tasks: add-event-push-model

## 1. 参数与通道侧

- [x] 1.1 `zoo_framework/params/event_params.py`：新增 `PUSH_MODEL_ENABLED`（`event:pushModelEnabled`，默认 False）与 `PUSH_FALLBACK_TIMEOUT`（`event:pushFallbackTimeout`，默认 1.0）
  - 实测：两键以 `param(value=…, default=…)` 声明于 `zoo_framework/params/event_params.py`；缺省与 NFR「默认关闭」一致（`test_missing_keys_keep_conservative_defaults` 同族断言在 batching 侧覆盖同一路径）
- [x] 1.2 `zoo_framework/event/event_channel.py`：懒创建 `threading.Condition`（开关门控）+ `push_event` / `dispatch` 成功后 `notify_all()`（入队成功才通知）
  - 实测：`EventChannel` 持 `_condition`（启用时构造，关闭态恒 `None`）+ `_ensure_condition()` 首读补建兜底；`push_event` 在**成功入队之后**才 `_notify_ready()`（入队异常路径不通知），`dispatch` 同；`notify_ready` 未启用时直接返回（零锁零分配）。`condition` 只读属性对外暴露
- [x] 1.3 测试：通知在入队后发出（fake 条件变量录制调用）、关闭时 Condition 不被创建、回队路径同样通知
  - 实测：`tests/test_event_push_model.py`——`TestConditionGating` 4 用例（启用即持有 Condition、关闭恒 None、关闭态生产路径为空操作且不影响入队、开关打开后首读补建且补建出的 Condition 真能被唤醒）；`TestNotifyWakesWait` 4 用例（push_event 唤醒、队列已非空时立即返回、缺位时等满兜底、dispatch 同样唤醒）；`TestRequeueAlsoNotifies` 1 用例（留额回队同样唤醒，且回队后事件在队列、重试已递减、无死信）。唤醒类用例均带「兜底拍 3s vs 提前唤醒 < 1s」的牙齿断言

## 2. 消费侧挂起

- [x] 2.1 `zoo_framework/workers/event_worker.py`：排空后（全部通道空且开关开）对所有通道 Condition `wait(timeout)`；唤醒/超时后走正常排空（消费主体复用既有路径）
  - 实测：实现把等待放在**消费轮开头**（`_execute` 首行，开关开时 `_push_wait(PUSH_FALLBACK_TIMEOUT)`），锁内队列非空即短路返回，随后复用既有排空主体——与设计措辞「排空后挂起」行为等价（轮首非空则不等待、轮首为空则等待），且避开了「等待后加全空守卫」会饿死竞态入队事件的坑（`_execute` 注释记录该约束）。关闭态 `_push_wait` 是零开销空操作（`wait_ready` 立即返回 False）
- [x] 2.2 测试：挂起与唤醒端到端（生产者入队且消费者消费）、兜底超时后恢复扫描、推模型关闭时走既有心跳轮询（行为等价断言）
  - 实测：`TestWorkerSuspend`（端到端本轮被唤醒完成排空投递、全空兜底快速返回、关闭态按既有路径消费且 Condition 恒 None）、`TestFallbackResumesScan::test_missed_notify_fallback_resumes_and_consumes`（**绕过 notify 直接入队**模拟生产者漏通知：断言不会被立即唤醒、须在兜底拍内恢复、恢复后积压必被消费）

## 3. 语义守护

- [x] 3.1 测试：事件去向恰好其一（投递/回队/死信）在推模型开/关两态下一致（复用既有 event 测试形态）
  - 实测：`TestOutcomeParityAcrossSwitches::test_outcomes_identical_with_push_on_and_off`——同一组三事件（可投递 / 留额 / 无留额）分别在开关两态下跑一轮，先断言两态观测**完全相同**，再逐项断言去向（投递恰好一次、留额恰好回队一次、无留额恰好死信、三者计数之和 = 事件数）。注入「回队路径静默丢弃」时该用例变红，且红在逐项断言而非两态相等
- [x] 3.2 关闭零影响断言：无 Condition 分配、生产路径无新增分支开销（可用源码级断言或行为等价）
  - 实测：`TestConditionGating::test_disabled_producer_path_is_noop`（关闭态 `notify_ready()` 是空操作、不懒建 Condition、不影响入队）+ `test_disabled_worker_behaves_as_polling`（关闭态消费按既有路径、Condition 恒 None）+ `test_channel_condition_is_none_when_disabled`。把实现改成「关闭态也分配 Condition」时三条全部变红

## 4. 验收与归档

- [x] 4.1 端到端：开启后空闲期为零扫描（挂起）、事件入队到消费延迟 < 心跳间隔
  - 实测：`TestIdleSuspendEndToEnd::test_idle_suspends_without_scanning_then_wakes_quickly`——兜底拍拉到 3s 以排除轮询混淆；对 `channel.size()` 计数：0.3s 空闲后本轮仍未返回，且随后 0.2s 窗口内**零新增扫描**（真挂起，非空转）；入队到本轮完成排空的延迟 < `EVENT_DELAY_TIME`（心跳间隔）且 < 1s（提前醒来只可能是 notify 的功劳）；被唤醒的这一轮完成了投递
  - 边界（如实记录）：该收益限于**等待窗口内**的入队。等待窗口在消费轮开头，轮与轮之间仍由 `BaseWorker.run()` 的 `event:delay` 隔开（waiter 跳过 in-flight Worker），故最坏延迟与合入前相同。详见 design.md「开放项」
- [x] 4.2 全量门禁：pytest / ruff / mypy / `openspec validate add-event-push-model --strict`
  - 实测（3.13.14）：`pytest` **1134 passed**（含本次新增的 6 个推模型用例，基线 1124）；`ruff check zoo_framework tests` All checks passed；`ruff format --check zoo_framework`（CI 口径）107 files already formatted；`mypy zoo_framework` Success: no issues found in 107 source files；`bandit -r zoo_framework -c .bandit.yaml` 0 issues；`uv lock --check` 通过；`openspec validate add-event-push-model --strict` valid
  - 实测（3.11.15，下界解释器）：本次涉及的三个测试文件 **38 passed**（含全部计时断言——断言留了宽松余量以适配 3.11/3.12 的 ~15.6ms 定时器粒度）
  - 未执行项（如实记录）：`mkdocs build` **无法执行**——本机离线，装不出 mkdocs/mkdocs-material/mkdocstrings；已改为核对文档改动（链接目标存在）与全量 pytest 中的文档一致性用例
  - 断言注入（assertion-integrity，串行、带 `VIOLATION-` 标记）：V2 `notify_ready` 早返回（吞掉唤醒）→ **6 个用例**变红（补建唤醒、push_event 唤醒、dispatch 唤醒、端到端本轮唤醒、回队唤醒、空闲挂起端到端）；V3 去掉 `wait_ready` 锁内非空短路 → `test_wait_ready_returns_true_immediately_when_queue_nonempty` 变红；V4 `wait_ready` 不等兜底拍 → 8 个用例变红（含 `test_wait_ready_fallback_after_timeout` 与漏通知恢复用例）；V5 关闭态也分配 Condition → 4 个「关闭零分配」用例变红。按 md5 逐字节还原（`event_channel.py` 6a056df6… 与注入前一致），`grep -rn "VIOLATION-" zoo_framework tests` 无残留
  - 说明：V2 首轮只红 1 个用例，暴露出 4 个唤醒用例当时靠 0.05s 兜底拍「蒙对」——已按断言有效性规则补上「兜底拍 3s vs 提前唤醒 < 1s」的直接断言，重注入后 6 个用例变红
- [x] 4.3 docs/ 更新事件一节
  - 实测：`docs/guides/event-pipeline.md`「节拍与推送模型」按实现重写——等待窗口的位置与边界、兜底不会困住事件、关闭态走原有轮询路径，并明确「最坏延迟不变，要缩短最坏延迟应调 `event:delay`」（合入前的表述「事件到达即投递，不再等节拍」与实现不符，已更正）；`docs/guides/config-reference.md` 补四键并注明 `pushFallbackTimeout` 的逐通道串行乘法关系
- [x] 4.3b `/opsx:archive` 后核对 `openspec/specs/event-push-model/spec.md` 与实现一致（归档期任务；本会话现场逐条核对，未派 agent）
  - 核对方式：归档后逐条 Requirement / Scenario 对照 `event/channel/event_channel.py`（`push_event` / `dispatch` / `wait_ready` / `notify_ready` / `_ensure_condition`）与 `workers/event_worker.py::_push_wait`，复用 4.2 的注入证据（V2/V3/V4/V5/V6）
  - 生产者通知 ↔ `push_event` 成功入队后 `notify_ready()`；「通知本身 MUST NOT 引入可观测延迟」为设计级主张（无竞争 `Condition` + `notify_all`），无单测，属构造性保证——**如实记录为未单测项**
  - 消费者挂起与兜底 ↔ `_push_wait` 逐通道 `wait_ready(timeout)` + 锁内非空短路（V3 证明该短路被断言守着）；关闭时保持轮询行为 ↔ V5（关闭态零 `Condition` 分配）
  - 语义不变 ↔ `TestOutcomeParityAcrossSwitches`：投递 / 回队 / 死信三类去向逐字节一致（V6 证明有牙齿）；**边界如实记录**：过期事件路径未纳入该对照，其行为由逐事件路径原样保留
  - 归档卫生：`## Purpose` 占位符已填成能力说明（归档工具留的 `TBD - created by archiving change …` 会让 `validate --specs --strict` 报占位符 WARNING）
  - 结论：**规格与实现一致，无差异项**；除 Purpose 外未改动规格文本
