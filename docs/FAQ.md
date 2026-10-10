# 常见问题

## 它和 Celery 有什么区别？我该用哪个？

**需要跨机器就用 Celery**，这是正确答案，不是退让。

Zoo Framework 是**进程内**的：没有独立 worker、没有 broker、没有分布式调度。
它赢的那一行是"**无外部依赖、无 broker、无 cron 守护进程，但依然有调度、可观测、可持久化**"。

判断方法：如果你的任务需要在另一台机器上跑 → Celery。如果它就该待在你的进程里 → 继续往下看。

## 不装 Redis / RabbitMQ 能跑后台定时任务吗？

**能。** 这是本框架的核心场景。`pip install zoo-framework`，写一个 `BaseWorker` 子类，
`master.register_worker(...)` 然后 `master.run()`。全程没有任何外部服务。

## 它和 APScheduler 有什么区别？

APScheduler 的做法是**调度函数**；本框架管的是**任务单元的生命周期**。

具体地，你多得到这些：Worker 生命周期（`_on_create` / `_destroy` / `_on_error` / `_on_done`）、
在飞去重（同一个 Worker 不会并发派发两次）、超时**观察与熔断**、
事件管道（通道隔离 / 优先级 / 重试 / 死信）、内建状态持久化（原子替换 + 滚动备份）、
以及作用域容器。

**但 APScheduler 在 cron 表达式上比本框架强**——它支持，本框架不支持（只有固定 `delay_time` 轮询）。
需要 cron 就用 APScheduler。

## 支持多进程吗？

**不支持，未实现。** 模式常量 `RUN_MODE_PROCESS` 是占位，请求它会抛 `NotImplementedError`。

## 支持 cron 表达式吗？

**不支持。** 只有固定 `delay_time` 轮询。需要 cron 表达式请用 APScheduler。

## 任务卡住了会怎样？会被强杀吗？

**不会被强杀。** `run_timeout` 的行为是**观察并停止派发**——框架不再把这个 Worker 排进调度，
但**不会强制终止**正在执行的 Worker。

这是刻意的：Python 里没有安全的线程强杀机制，假装有它会制造更难查的问题。
你需要自己在 `_execute()` 里响应取消信号。

## 重启之后任务状态会恢复吗？

**会**，前提是你用了状态机（`StateMachineManager`）。

状态由 `StateMachineWorker` 周期性落盘、停机时再存一次：先写 `.tmp` 再原子替换，
并在同级的 `backups/` 保留最近 5 份。

> **恢复语义是「整表替换」**，不是逐键合并。这一点在迁移或手工改过状态文件时要留意。

## 为什么叫 Zoo？这些名字（Worker / Master / Waiter / Cage）到底对应什么？

名字来自动物园隐喻，但**隐喻只影响命名，不影响语义**——这是一处已知的设计债。

| 代码里的名字 | 实际是什么 |
|---|---|
| `BaseWorker`（🦁 Worker） | 任务执行单元 |
| `Master`（👨‍🌾 Master） | 生命周期入口 |
| `core/waiter/`（🍽️ Waiter） | 调度器 |
| `ScopedContainer`（🏠 Cage） | 作用域容器 |
| `EventNode` / `EventChannel`（🍎 Event） | 进程内消息 |
| `EventFIFO`（🥘 FIFO） | 每通道一条独立队列 |
| `EventReactor`（📢 Reactor） | 事件响应器 |
| `StateMachineManager`（🔄 StateMachine） | 状态读写与持久化 |

如果你觉得某个名字难懂，那不是你的问题——欢迎提 issue 建议功能名别名。

## 它和 AI Agent 有什么关系？

本框架的扩展面被刻意做窄，并把所有失败都做成**大声报错**（不静默降级）。
这一点对**生成的代码**比对人写的代码更重要：agent 无法发现自己被静默降级了，
而一个响亮的错误是它自我纠正所需要的信号。

具体地：未实现的调度模式抛 `NotImplementedError`、无法识别的 run-policy 抛 `ValueError`、
导入不存在的公开名抛 `ImportError`、文件编码异常会发一条点名该文件的警告。

## 生产环境有人用吗？

**目前没有可核实的外部使用者。** 维护者自己的私有项目在用，但那**无法被读者核实**，
因此不作为证据列出。

这是一个诚实的空缺。如果你在生产中用上了，欢迎提 PR 加入
[`ADOPTERS.md`](https://github.com/YearsAlso/zoo-framework/blob/dev/ADOPTERS.md)。

## 为什么要求 Python 3.13+？

因为这是当前 `pyproject.toml` 里的 `requires-python`。

**但这个门槛是被认为偏高的**——它把大量仍在 3.10–3.12 的环境排除在外，
也使得本框架难以成为其他项目的可选依赖。降低门槛的工作在 issue #124 中跟踪。

## 装不上 / 版本不对怎么办？

见[安装](install.md)。最常见的两个坑：

- Python 版本低于 3.13 → 先升级解释器
- 用了 `uv sync` → 仓库的 `uv.lock` 当前与 `pyproject.toml` 不一致，请用 `pip install -e ".[dev]"`

## 我发现文档和代码不一致

**大概率是文档的问题，而且现在能被 CI 抓到了。**

仓库有 `tests/test_doc_consistency.py`，它会校验：
文档中的导入语句真的能执行、API 参考页的指令指向真实可导入的对象、相对链接指向存在的文件。

如果你发现了它没抓到的不一致，请提 issue——那说明检查还需要加强。
