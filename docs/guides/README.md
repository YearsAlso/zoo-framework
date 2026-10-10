# 指南

教程是**线性**的（一步步走）；指南是**主题式**的（按"我要做 X"查）。两者互补。

| 指南 | 回答 |
|---|---|
| [配置参考](config-reference.md) | 有哪些配置键、默认值、怎么组合 |
| [超时与熔断](timeouts.md) | 任务卡住了怎么办、为什么不会被强杀 |
| [状态持久化](state-persistence.md) | 怎么让状态活过重启、备份在哪、恢复语义是什么 |
| [事件管道](event-pipeline.md) | 两个任务之间怎么通信、优先级与重试 |
| [作用域容器](container.md) | 怎么跨任务共享实例而不破坏类型契约 |
| [与其它方案对比](comparison.md) | 什么时候该用 Celery / APScheduler / 裸 threading |
