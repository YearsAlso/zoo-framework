# event-dispatch 规格变更（fix-reactor-timeout delta）

## MODIFIED Requirements

### Requirement: 事件投递的并发原语 MUST 独立于 greenlet 且超时与异常可观测

事件消费路径派发响应器的执行原语 SHALL 为基于 OS 线程的执行器，MUST NOT 依赖 gevent 或 greenlet（框架的运行依赖中 MUST NOT 出现两者）。对派发结果的等待 MUST 有界超时；等待时长 SHALL 为本轮派发集中各响应器生效超时的最大值。生效超时 SHALL 两级解析：响应器声明值优先，未声明（非正值）时跟随全局 `event:timeout`；等待覆盖每个响应器自身的生效超时，超时后仍未结束的响应器 MUST 可观测地上报，MUST NOT 随超时静默消失；上报 MUST 携带该响应器的名称与对应事件主题（批量路径携带所涉主题集合），未声明生效值的响应器超出全局约定时按未完成上报。响应器抛出的异常 MUST 可观测地上报，MUST NOT 被吞掉，上报 MUST 携带响应器名称与事件主题。

#### Scenario: 无 greenlet 的构建上事件管道照常工作
- **WHEN** 在不安装 gevent 的 Python 构建上导入并运行框架，发布并消费一个事件
- **THEN** 事件被投递到响应器，不出现 ImportError，也不出现功能降级

#### Scenario: 超时后未结束的响应器被可观测上报
- **WHEN** 某响应器执行时长超过其生效超时
- **THEN** 产生包含该响应器名称与事件主题的告警日志，消费循环继续，该响应器的结果不被静默回收

#### Scenario: 响应器异常被可观测上报
- **WHEN** 响应器在执行体内抛出异常
- **THEN** 异常被记入日志且携带响应器名称与事件主题，本轮其余事件的投递不受影响

#### Scenario: 声明了合法慢的响应器不触发告警
- **WHEN** 响应器声明了大于其执行时长的生效超时
- **THEN** 该响应器执行期间不产生"未完成"告警，全局超时对其余未声明响应器继续生效
