## Purpose（本变更新增条款）

事件投递并发原语的独立性（不依赖 greenlet）与 join 超时/异常的可观测性。

## MODIFIED Requirements

### Requirement: 事件通道的消费路径 MUST 真正投递到响应器

事件通道的消费路径 SHALL 把队列中已被选中的事件交给对应响应器处理。响应器被调用时 MUST 收到该事件的 topic 与 content，且二者 MUST NOT 互换。消费过程中取出的事件 MUST 有确定去向——被投递、被回队、或被记入可观测的失败记录；MUST NOT 出现"取出后既未投递也未回队"的情况。队列在"检查长度"与"取出元素"之间变空 MUST NOT 导致消费路径抛出异常。并发投递 SHALL 基于线程执行器执行，MUST NOT 依赖 gevent / greenlet。

#### Scenario: 已入队的事件被响应器处理
- **WHEN** 一个事件被入队到某通道，该通道的该主题下存在响应器，随后执行一次通道消费
- **THEN** 该响应器的回调被调用一次

#### Scenario: 响应器收到的主题与内容不互换
- **WHEN** 以主题 T 与内容 C 入队事件，随后执行一次通道消费
- **THEN** 响应器收到的主题为 T、内容为 C

#### Scenario: 队列在取出瞬间变空不导致异常
- **WHEN** 队列在检查长度与取出元素之间被并发清空
- **THEN** 消费路径不抛出异常

#### Scenario: 无响应器的事件有确定去向
- **WHEN** 取出的事件在其通道与主题下没有任何响应器
- **THEN** 该事件在声明了剩余重试次数时被回队，否则被记入可观测的失败记录，不被静默丢弃

#### Scenario: 响应器抛异常时事件有确定去向
- **WHEN** 响应器处理事件的过程中抛出异常
- **THEN** 该事件被回队或被记入可观测的失败记录，不被静默丢弃

## ADDED Requirements

### Requirement: 事件投递的并发原语 MUST 独立于 greenlet 且超时与异常可观测

事件消费路径派发响应器的执行原语 SHALL 为基于 OS 线程的执行器，MUST NOT 依赖 gevent 或 greenlet（框架的运行依赖中 MUST NOT 出现两者）。对派发结果的等待 MUST 有界超时；超时后仍未结束的响应器 MUST 可观测地上报，MUST NOT 随超时静默消失。响应器抛出的异常 MUST 可观测地上报，MUST NOT 被吞掉。

#### Scenario: 无 greenlet 的构建上事件管道照常工作
- **WHEN** 在不安装 gevent 的 Python 构建上导入并运行框架，发布并消费一个事件
- **THEN** 事件被投递到响应器，不出现 ImportError，也不出现功能降级

#### Scenario: 超时后未结束的响应器被可观测上报
- **WHEN** 某响应器执行时长超过 join 超时
- **THEN** 产生包含数量信息的告警日志，消费循环继续，该响应器的结果不被静默回收

#### Scenario: 响应器异常被可观测上报
- **WHEN** 响应器在执行体内抛出异常
- **THEN** 异常被记入日志而非静默丢弃，本轮其余事件的投递不受影响
