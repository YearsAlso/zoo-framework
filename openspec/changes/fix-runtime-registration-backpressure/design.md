## Context

容量准入今天只有一条路径：`BaseWaiter.call_workers`（启动期 muster）→
`model.prepare_workers(workers)` → `model.start(core)`。`prepare_workers` 是模型对「Worker 数是否
超过池容量」的裁决点：`reject` 抛 `ValueError`、`expand` 放宽 `effective_pool_size`、`queue` 保持
尺寸。

`BaseWaiter.add_worker`（运行期注册）只做 `core.add_worker`，绕过了整个裁决点，因此背压策略对运行
期新增完全失效。

## Decision

让运行期注册与启动期**走同一套准入**：`add_worker` 构造「候选调度列表（现有 + 新增）」，先交给
`self.model.prepare_workers(candidate)`，通过后再 `core.add_worker(worker)`。

- **先裁决后写入**（而非先写入再回滚）：被拒时调度列表**不变**，无需回滚路径。
- 线程模型 `prepare_workers` 恒返回 0（无容量概念），运行期注册不受影响。
- `reject`：候选数超容量即抛 `ValueError`（复用既有报错文案），新增 MUST NOT 被静默纳入。
- `queue`：照常接纳，超出的排队（既有语义）。

### expand 必须对运行中的池真实生效

`prepare_workers` 在启动期的语义是「建池前先放宽尺寸」。但运行期调用时容器可能**已经在跑**：若只把
`effective_pool_size` 改大而不动线程，就会得到一个「数字变了、行为没变」的静默 no-op——正是本仓库
反复禁止的「调用成功但无效果」。

因此 `ThreadPoolModel.prepare_workers` 在 `expand` 放宽后，若容器已建立（`_tasks is not None`）就
调用幂等的 `_ensure_threads(effective_pool_size)` 增补线程；`start` 改为复用同一 `_ensure_threads`
（建队列 + 补齐线程），语义与原先一致（首次按生效尺寸建池、可重复调用），并新增运行期增补能力。
**线程只增不减**——缩容仍是 `teardown` 的职责。

### 停机不被复活

`teardown` 把 `_tasks` 置空、`_threads` 清空，故停机后 `_tasks is None`：运行期注册既不会增补线程、
也不会重建容器；`execute_service` 因 `stopped` 标记直接返回——停机语义不变（既有用例
`test_no_new_dispatch_after_shutdown` 守护）。

## Non-goals

- 不改变背压策略的合法取值集合与报错文案。
- 不改变 `queue` 的排队语义与 `teardown` 的「丢弃未开始任务」语义。
- 不为线程模型引入容量概念（它声明为 `unbounded`）。
- 不处理 `Master.register_worker` 在准入被拒时「注册表已写、调度未纳」的非原子性（属 `Master` 层，
  另行评估）。

## Language

正文与注释用中文；代码 docstring 保持 Google 风格（`Args:` / `Returns:` / `Raises:`）。
