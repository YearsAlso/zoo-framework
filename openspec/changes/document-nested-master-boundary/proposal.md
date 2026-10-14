## Why

消费方 `zoo-code-agent` 在其 `ROADMAP.md` 的 Later 里记着一条**实测**约束：

> sub-agents：**同进程不能嵌套 `Master`**（框架容器的线程校验会拒绝，实测），必须跨进程。

问题在于这条约束**只存在于消费方的文档里**。框架自身既没把它写成契约，也没在文档里
说明"嵌套 / 多租户 / 一个进程多个运行时该怎么做"。于是任何做 sub-agent、多租户、
或想让一个进程承载多个运行时的使用者，都会踩同一块地——**而且是在运行期才踩到**。

本提案的立项依据是 issue #248，其正文把该约束定性为"刻意设计"，并给出两个候选方向：
"永久约束 + 文档化"（成本极低）与"支持嵌套"（数周级设计）。维护者已裁决取**前者**。

## 必要的实测更正（本提案与 issue 正文的差异）

issue 正文写着「**若**同进程二次构造必然不成立，就让它在构造期以明确错误拒绝」。
这个**条件句的前件在测量后不成立**，实测结果如下（`origin/dev` = `97c2175` 基线）：

| 场景 | 实测结果 |
|---|---|
| 同一线程先后构造两个 `Master` | **两次都成功，不抛异常** |
| 跨线程构造第二个 `Master` | 在 `Master.__init__` 内抛 `ValueError`，栈为 `WaiterResultReactor()` → `container.py:438` 的线程归属守卫 |

跨线程那条的报错原文是：

```
registration 'zoo_framework.reactor.waiter_result_reactor.WaiterResultReactor'
is declared as 'single_thread'(single-thread only), bound to thread 34704;
the current thread 3328 may not consume it; ...
```

它**指不到病根**：使用者读到的是框架内部某个注册项的线程归属，而不是"你在同一个进程里
放了两个 Master"。

更关键的是，既有能力规格 `worker-lifecycle` 里有一条 MUST 级别的场景：

```
#### Scenario: 构造过程可重复
- **WHEN** 先后两次以默认配置构造框架管理器
- **THEN** 两次均成功，不抛出异常
```

`tests/test_runtime_defects.py:63` 的 `test_master_construction_is_repeatable` 正守这条。
因此**「构造期一律拒绝」会直接违反一条既有 SHALL 场景**，本提案不取该路径。

真正不成立的不是"构造了两次"，而是**两个 Master 同时处于运行态**：`WorkerRegistry` 经容器注册为
进程级实例（`register_process_instance(WorkerRegistry, thread_safety=INSTANCE_GUARANTEED)`），
两个 waiter 会各自遍历**同一份**注册表并派发同一批同名 Worker。

## What Changes

- **新增运行期唯一性约束**：同进程内已有一个处于运行态的 `Master` 时，第二个 `Master`
  进入运行时 MUST 被拒绝，且错误信息 MUST 指明病根与受支持的替代形态。
- **修正既有的模糊报错**：跨线程构造第二个 `Master` 时，今天抛出的是容器内部注册项名；
  改为在 `Master.__init__` 早期识别该场景并给出同一套明确文案。
- **文档化边界**：`docs/ARCHITECTURE.md` 的容器一节与 `docs/FAQ.md` 各补一段，写明
  「一个进程一个 Master」的原因，以及**受支持的替代形态**（独立进程；进程池 + 事件回传）。
- **保持既有构造契约不变**：`worker-lifecycle` 的「构造过程可重复」场景与对应用例
  **保持不变**，本变更 MUST NOT 使其变红。

非 BREAKING：不使用嵌套 / 多运行时形态的调用方，行为逐字节不变。

## Capabilities

### New Capabilities

- `nested-master-boundary`: 同进程运行时的边界语义——活跃 `Master` 的进程内唯一性、
  越界时的拒绝语义与错误信息要求、以及该边界与替代形态必须被文档化。

### Modified Capabilities

（无。`worker-lifecycle` 的既有「构造过程可重复」场景在本变更下**继续成立**，其 Requirement
不发生变更，故不产生 delta。）

## Impact

**受影响代码**

- `zoo_framework/core/master.py`：`Master.__init__` 早期加跨线程重复构造的识别；`Master.run()`
  入口加活跃实例的唯一性判定与拒绝。
- `zoo_framework/core/container/`：判定所需的运行态登记须经容器持有（可 `reset()`），
  **MUST NOT** 引入容器之外的手工复位全局状态——否则 `tests/conftest.py` 的隔离夹具
  将无法覆盖它（该夹具只覆盖容器、类级注册表与 `WorkerRegistry` 缓存三类载体）。

**受影响文档**

- `docs/ARCHITECTURE.md`（容器一节）、`docs/FAQ.md`（新增一节）。

**受影响测试**

- `tests/test_runtime_defects.py`：`test_master_construction_is_repeatable` 必须**保持绿**
  （反向验证本变更未误伤既有契约）；新增同进程活跃唯一性的用例。

**下游**

- `zoo-code-agent#43`「子 agent：跨进程执行、预算切分与结果回收」的前置结论由本变更给出，
  该 issue 可直接引用本变更的文档段落而无需重新实测。

**依赖**

- 无新增第三方依赖。
