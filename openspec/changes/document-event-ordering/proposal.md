# 提案：document-event-ordering —— 把「FIFO 的顺序保证」写进规格与文档

## Why

issue #230 报的现象：向同一通道按顺序入队两个事件后，**完成顺序与入队顺序无关**
（实测 `['B', 'A']`，入队是 `['A', 'B']`），而且对**同一个响应器**也成立——不是
"不同响应器之间并发"，而是"同一响应器的多次调用会重叠"。这一点**没有写在任何文档里**。

### 先判断：FIFO 的完成顺序是框架承诺的语义吗？

**不是。** 依据：

1. 消费侧的执行原语是**共享线程池**（`EventWorker._executor`，`event:executor:workers`
   默认 8）：`_execute` 按队列顺序**弹出**事件，但每个事件都 `submit` 给执行器，
   同一响应器的多次调用天然重叠，完成顺序由各次执行的实际结束时刻决定。
2. 通道 FIFO 的既有规格只说"消费过程中取出的事件 MUST 有确定去向"与"按弹出顺序处理"，
   从未承诺"完成顺序等于入队顺序"；`event-dispatch-batching` 的「语义与顺序不变」一条
   用的是"通道内处理顺序（仍按弹出顺序执行响应器）"这一含糊表述——它在批量路径上指
   "批内按弹出顺序串行"，在逐事件路径上却容易被读成"完成顺序"。
3. 优先级计算（`EventPriorityCalculator` 的年龄加成）本就会改变事件相互顺序，
   "入队顺序 = 执行顺序"从来不是可依赖的不变量。

**结论**：这不是行为缺陷，而是**未文档化的惊喜**（undocumented surprise）。按 issue
给出的两个方向，本变更走"把真实的顺序保证写进规格与文档"这一支，**不改变运行时行为**。

## What Changes

- `event-dispatch` 的「事件通道的消费路径 MUST 真正投递到响应器」补入顺序语义：
  FIFO 只承诺**出队/投递顺序**；响应器执行并发进行，完成顺序 MUST NOT 被承诺为入队顺序；
  需要顺序完成的使用方 MUST 自行串行化，或改用批量投递；该语义 MUST 写在消费侧类说明里。
- `event-dispatch-batching` 的「语义与顺序不变」澄清：批内同响应器的事件按弹出顺序**串行**
  执行（故完成顺序 = 弹出顺序），这是"需要顺序完成"的现成入口，且是**进程级**开关；
  关闭批量投递时不承诺完成顺序。
- `EventWorker` 类说明新增 Ordering 段（issue #230），并补一处中文行注释点明提交即并发。
- 新增 `tests/test_event_ordering.py`：把真实顺序语义（出队顺序 = 入队顺序；缺省路径完成
  顺序由实际完成时刻决定；批量路径串行）与"类说明已写明该语义"一起变成可执行断言。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `event-dispatch`：修改「事件通道的消费路径 MUST 真正投递到响应器」——补顺序语义的
  SHALL（只承诺投递顺序、不承诺完成顺序、顺序语义须写明）+ 3 条 Scenario。
- `event-dispatch-batching`：修改「语义与顺序不变 (Semantics and Order Preserved)」
  ——澄清批内串行完成语义与"关闭时不承诺完成顺序" + 2 条 Scenario。

## Impact

- **代码（仅注释与 docstring）**：`zoo_framework/workers/event_worker.py` 的类说明与
  一处行注释。**无任何运行时行为变化**。
- **测试**：新增 `tests/test_event_ordering.py`（4 条）。
- **不在范围**：不做"按响应器声明串行"的配置入口（issue 的方向 ②）——那是新增功能与
  设计分歧，列入待维护者裁决项（见 design.md 的 Open Questions）。
- **不在范围（所有权）**：`docs/` 站点的事件一节归其他所有者；本变更只在规格与代码
  docstring 内写明顺序保证。
