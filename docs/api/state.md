# 状态

按「作用域 + 键路径」读写状态，支持点分嵌套、变更观察者与持久化。

```python
from zoo_framework.statemachine import StateMachineManager
```

::: zoo_framework.statemachine.state_machine_manager.StateMachineManager

## 作用域与节点

::: zoo_framework.statemachine.state_scope.StateScope
::: zoo_framework.statemachine.state_node.StateNode
::: zoo_framework.statemachine.base_state_machine.BaseStateMachine

## 索引与类型

::: zoo_framework.statemachine.state_node_type
::: zoo_framework.statemachine.state_node_index
::: zoo_framework.statemachine.state_index_factory.StateIndexFactory
::: zoo_framework.statemachine.state_index_factory.QueryableIndex

## 状态 effect

::: zoo_framework.statemachine.state_effect.StateEffect
::: zoo_framework.statemachine.state_effect_scheduler.StateEffectScheduler

## 任务队列

与 Worker 解耦的任务值对象与落到状态机持久化作用域的可持久化队列
（详见[状态持久化](../guides/state-persistence.md)的「任务队列」）。

```python
from zoo_framework.tasks import Task, TaskQueue, TaskStatus
```

::: zoo_framework.tasks.task.Task
::: zoo_framework.tasks.task.TaskStatus
::: zoo_framework.tasks.task_queue.TaskQueue
