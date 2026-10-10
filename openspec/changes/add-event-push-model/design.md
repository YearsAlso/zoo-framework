# Design: add-event-push-model

## Context

见 proposal.md。现状：`EventWorker._execute` 在 `is_loop=True` 的固定心跳消费循环里被 waiter 调度（每轮扫描全部通道 `.size()`）。空闲空转 + 平均半拍心跳延迟。

## Goals / Non-Goals

**Goals**
- 通道无事件时消费者挂起（零空转），生产者入队即唤醒
- 兜底超时防丢失唤醒（notify/wait 竞态、生产者异常）
- 关闭（默认）时零影响：不建 Condition、不取锁、行为与合入前一致

**Non-Goals**
- 不做跨进程事件总线（epoll 的 socket 场景——本 change 是进程内队列）
- 不改事件去向/重试/死信/优先级语义
- 不动 executor 派发形态（那属于 optimize-event-dispatch-batching）

## Decisions

### D1: 进程内对应物 = per-channel `threading.Condition`，非 epoll/selectors

**选择**：`EventChannel` 持有一个懒创建的 `threading.Condition`（锁为普通 `Lock`）；生产路径入队成功后 `notify_all()`（唤醒单消费者服务也正确）。`EventWorker` 排空后若全部通道为空，对所有 channel_condition `wait(timeout)`。
**理由**：epoll 的本质是「等就绪集合的任一成员」，进程内等价物就是条件变量；per-channel 锁阵线避免全局单锁在多通道批处理下串行化；`selectors`/`loop` + 自建 socketpair 是为 fd 世界设计的间接层，进程内是重avo与语义错配。
**备选**：全局单 Condition（实现更少一把锁，但多通道唤醒惊群；通道数少时其实也可接受——若验收发现 per-channel 锁开销显著可退化为全局）；`Event` 每通道一标志位（一次性唤醒，_MULTI 消费者不适用——框架当前每进程一个 EventWorker，但语义上锁+Condition 更通用）。

### D2: 懒创建 + 开关门控，关闭零分配

**选择**：Condition 由推模型启用开关控制——关闭时 `EventChannel` 根本不创建 Condition 对象，生产者路径零新增分支（一个 bool 检查）；启用时在首次 notify 前 `ensure_notified()`.
**理由**：spec 要求关闭时零影响（不取锁、不进分支）；懒创建避免无事件通道白付一把锁。

### D3: 兜底双层 = wait(timeout) + 状态标志

**选择**：wait 的 timeout 取新参数 `event:pushFallbackTimeout`（默认保守值，如 1s 与现有 EVENT_DELAY_TIME 同量级）；同时保留每轮扫描后的存量语义——wait 返回（被 notify 或超时）后走一轮正常排空，排空逻辑完全复用既有代码路径，WAIT 不改变消费主体。
**理由**：丢失唤醒最坏退化為「多等一个兜底拍」，不损语义；消费主体不变使本变更的面剪小。

### D4: notify 挂点 = `EventChannel.push_event` / `dispatch`，不在 FIFO 层

**选择**：notify 挂在 `EventChannel`（通道对象知道自己的 Condition），`EventFIFO`/`BaseFIFO` 保持纯队列不动。
**理由**：FIFO 是通用容器（DelayFIFO/SingleFIFO 共用基类），不应耦合事件语义；通道是事件域的对象，锁阵线归属它。回队路径（`push_event` 处理重试）也经同一入口，天然覆盖。

### D5: 参数键

`event:pushModelEnabled`（默认 false）、`event:pushFallbackTimeout`（默认 1.0s，秒）。加入 `EventParams`（lazy import 纪律既有）。

## Risks / Trade-offs

- [丢失唤醒] → Count 与队列非空可见性（notify 在入队成功后同锁域）+ 兜底超时双保险
- [多消费者惊群] → 当前单消费者不受影响；将来多消费者时 notify_all 与批处理配对（留观察）
- [锁阵线与 deque 操作不一致] → 挂点在 EventChannel 层，语义上「入队成功后通知」，不与 БaseFIFO 内部锁交叉（BaseFIFO 无锁）

## Migration Plan

1. 默认关闭合入（零变化）
2. 实验项目开启 `event:pushModelEnabled=true` 验证空闲零空转与投递延迟
3. 回滚 = 关开关

## Open Questions

- `EVENT_DELAY_TIME` 心跳在开启时是否保留为兜底轮询的顺带作用——倾向：开启后 wait(timeout) 即兜底，心跳循环参数复用其语义但不另行扫锚

## 实施记录（收口核对，2026-10-10）

- **等待位置**：D1/D3 措辞为「排空后、全部通道空时 wait」。实现把等待放在**消费轮开头**（`_execute` 首行，开关开时 `_push_wait(fallback)`），锁内先看队列非空即返回（短路）。两种放置行为等价：轮首已有事件则不等待直接排空；轮首为空则等待，等待窗口结束后照常排空。轮首形态另有一条必须遵守的约束——**不能**在等待后加「全空则跳过排空」的守卫（notify/超时与生产者入队之间无原子性，守卫求值瞬间恰好入队的事件会被饿到下一拍），理由写在 `_execute` 的注释里。
- **Condition 创建时机**：D2 措辞为「懒创建、首次 notify 前 ensure」。实现为「启用时 `__init__` 直接构造 + `_ensure_condition()` 首读补建兜底」——补建覆盖通道在开关打开**之前**创建的场景（运行期启用/热部署），避免通道永久失聪。关闭态仍是零分配（`condition is None`，生产者路径无锁无分支）。
- **`wait_ready` 返回值语义**：进入时队列已非空 → 立即 `True`（锁内短路）；被 notify 唤醒 → `True`；等满兜底仍空或未启用 → `False`。
- **兜底上界**：`_push_wait` **逐通道串行**等待，故单轮等待上界 = 通道数 × `event:pushFallbackTimeout`（配置参考已注明该乘法关系）。

## 开放项（不擅自改行为，留待决策 / 后续)

- **最坏延迟与合入前相同**：等待窗口位于轮首，轮与轮之间仍由 `BaseWorker.run()` 的 `event:delay`（默认 5s）隔开（waiter 跳过 in-flight Worker，见 `BaseWaiter.execute_service`）。故本变更的收益是「落在等待窗口内的入队即时投递」，**最坏延迟不变**（甚至多出等待窗口自身时长）。`docs/guides/event-pipeline.md` 已按此更正（合入前的文档措辞「事件到达即投递，不再等节拍」与实现不符）。若目标是最坏延迟，应调 `event:delay`，或另立变更让等待本身充当节拍——属行为变更，本变更未实施。
- **多消费者惊群**（Risks 项）：当前每进程一个 EventWorker，观察项，未处理。
