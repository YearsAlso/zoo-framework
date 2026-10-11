# event-push-model Specification

## Purpose
本能力给事件管道提供推送式消费模型：生产者入队即通知挂起的消费者，消费者无事件时挂起并有兜底超时，事件去向与关闭推模型时逐字节一致（不丢、不重复、不误死信）。

## Requirements

### Requirement: 生产者通知 (Producer Notification)

当事件通道入队成功（`push_value` / `dispatch`）时，通道 SHALL 通知消费者（进程内条件变量 notify），MUST NOT 在通知本身引入可观测延迟。通知 MUST 在与队列非空状态一致的锁序内进行，MUST NOT 产生丢失唤醒窗口（通知前队列非空状态已可见）。

#### Scenario: 入队唤醒挂起的消费者

- **WHEN** 生产者向通道入队一个事件且消费者正挂起等待
- **THEN** 消费者被唤醒并消费该事件
- **AND** 从入队到消费的延迟不受心跳间隔影响

#### Scenario: 通知不丢失

- **WHEN** 入队与 notify 完成后消费者才开始 wait
- **THEN** 消费者观察到队列非空并立即消费（_notify 前置状态可见性保证），无需等待下一次兜底超时

### Requirement: 消费者挂起与兜底 (Consumer Suspend and Fallback)

事件消费者 SHALL 在所有通道无事件时挂起等待（Condition.wait），并 SHALL 携带兜底超时：超时后重新扫描通道（防生产者侧异常导致的永久漏通知）。挂起行为 MUST 可被启用开关控制；关闭时 SHALL 保持既有固定心跳轮询行为不变。

#### Scenario: 无事件挂起零空转

- **WHEN** 所有通道队列为空且推模型启用
- **THEN** 消费者挂起等待而非按固定心跳空转轮询
- **AND** 空闲期间无扫描动作发生

#### Scenario: 兜底超时恢复扫描

- **WHEN** 生产者侧因异常未发出通知且队列实际非空
- **THEN** 兜底超时到达后消费者恢复扫描并消费积压事件
- **AND** 事件不会因漏通知而无限期滞留

#### Scenario: 关闭时保持轮询行为

- **WHEN** 推模型启用开关为假（含缺省）
- **THEN** 消费行为与本变更合入前完全一致（固定心跳轮询），不创建通知设施

### Requirement: 语义不变 (Semantics Preserved)

推模型 MUST NOT 改变既有事件去向语义：每个被取出的事件恰好被投递、被回队（带重试递减）或被记入死信三者之一；通道隔离、通道内顺序、过期判定、优先级语义均保持不变。

#### Scenario: 事件去向恰好其一

- **WHEN** 推模型启用且事件被消费者取出
- **THEN** 该事件被投递、回队或记入死信，三者恰好其一
- **AND** 与关闭推模型时的去向语义逐字节一致

#### Scenario: 关闭零影响

- **WHEN** 推模型关闭且框架合并本变更后运行
- **THEN** 事件管道行为与合入前等价（不进入 push-model 分支、不获取 Condition 锁）
