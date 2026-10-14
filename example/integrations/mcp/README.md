# MCP 集成示例：本地任务执行后端（长存活、带状态、不阻塞）

## 演示什么

MCP server 常被要求「调一次工具就把活干完」；一旦工具要做长耗时的事，直接 `await` 会把整个
server 卡住。本示例把任务投进 Zoo Framework 的事件管道，由一个**常驻 Worker 在后台线程**消费：

- **长存活**——常驻 Worker 与 server 同寿，工具调用之间它一直在跑。
- **带状态**——进度写入状态机并落盘，工具可随时查询，重启后从落盘值继续。
- **不阻塞**——`submit_job` 投递事件后立即返回，asyncio 事件循环不被占用。

## 怎么跑

`server.py` 是 **stdio** MCP server，由 MCP 客户端拉起，不直接手工运行。

```bash
pip install mcp                              # 不是 zoo-framework 的依赖
cd example/integrations/mcp                  # 本目录（config.json 会被框架自动读取）
python client_demo.py                        # 拉起 server 并调用两个工具
```

> stdio 传输的铁律：stdout 只允许走 JSON-RPC。示例把框架日志重定向到 stderr，自身输出也一律走
> stderr——这是 stdio MCP server 的通用约束，不是本框架特有的。

## 期望输出

```
tools: ['submit_job', 'server_status']
submit_job -> accepted: compile-report
...后台 Worker 处理中，等待数秒...
server_status -> {"ticks": 8, "jobsHandled": 1}
```

`ticks` 随常驻 Worker 持续推进增长；`jobsHandled` 是后台处理掉的任务数。状态存在本目录
`zooStates.pic`（运行时产物，已被 `.gitignore` 忽略），再次运行会从上次的值继续。

## 涉及哪些框架能力

- 常驻 Worker（`is_loop=True`）——长存活的后台执行单元。
- 事件管道（`@event` + `EventProvider.push`）——工具调用投递事件后立即返回。
- 状态机（`StateMachineManager`）——读进度、落盘、重启恢复。

## 何时不该用本框架

- **任务需要跨机器 / 分布式** → 用 **Celery**。本框架没有跨机器调度。
- **需要 cron 表达式** → 用 **APScheduler**。本框架只有固定 `delay_time` 轮询。
- **需要多进程执行** → 本框架**未实现**，请求未实现的模式会被显式拒绝。
- **工具本来就是瞬时同步的** → 直接 `return` 即可，不需要引入本框架。
- **要可靠投递（任务不丢）** → 本框架持久化的是**状态**，不是事件队列；进程在事件被消费前
  退出，该事件不会自动重放。需要投递保证请用带 broker 的队列。

（口径与根 `README.md` 的「同类方案对比」表、`llms.txt` 的 *When not to use it* 一致。）

## 可直接投给上游文档的说明文字

见同目录 [`upstream-doc-snippet.md`](upstream-doc-snippet.md)。
