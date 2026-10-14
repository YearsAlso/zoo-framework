# FastAPI 集成示例：用 Zoo 替代 `BackgroundTasks`

## 演示什么

`BackgroundTasks` 是在响应返回后跑的一次性回调：**没有状态、没有观测、进程重启即丢**。
本示例演示 Zoo Framework 补上的那部分：常驻 Worker 持续活在服务进程里，进度写入状态机并
**原子落盘**，因此**重启之后从上次的进度继续**——这是 `BackgroundTasks` 做不到的。

## 怎么跑

```bash
pip install fastapi uvicorn                 # 不是 zoo-framework 的依赖
cd example/integrations/fastapi             # 本目录（config.json 会被框架自动读取）
python -m uvicorn app:app --port 8010
```

另一个终端里：

```bash
curl -X POST localhost:8010/submit -d '"order-1"' -H "content-type: application/json"
curl localhost:8010/state
```

按 `Ctrl-C` 停掉，再用同一条命令启动一次——`GET /state` 里的 `ticks` 会从落盘值继续增长。

## 期望输出

```
[heartbeat_worker] tick #1
[heartbeat_worker] tick #2
...
[on_job] handled 'order-1' (total 1)
```

`GET /state` 返回 `{"ticks": N, "jobsHandled": M}`。重启后 `ticks` / `jobsHandled` 均不归零
（状态存在本目录的 `zooStates.pic`，由框架周期性 `os.replace` 原子写；该文件与 `logs/`、
`backups/` 都是运行时产物，已被 `.gitignore` 忽略）。

## 涉及哪些框架能力

- 常驻 Worker（`is_loop=True`）——请求之外也在推进的调度单元。
- 事件管道（`@event` + `EventProvider.push`）——`POST /submit` 立即返回，处理异步发生。
- 状态机（`StateMachineManager`）——按「scope + 键路径」读写并落盘，重启恢复。

## 何时不该用本框架

这张表是**范围声明，不是打分表**：

- **任务需要跨机器 / 分布式** → 用 **Celery**。本框架没有跨机器调度。
- **需要 cron 表达式** → 用 **APScheduler**。本框架只有固定 `delay_time` 轮询。
- **需要多进程执行** → 本框架**未实现**，模式常量是占位，请求它会被显式拒绝。
- **只需要请求返回后的一次性收尾** → 直接用 `BackgroundTasks` 就够了，不必引入本框架。
- **要可靠投递（任务不丢）** → 本框架持久化的是**状态机**，不是待处理事件队列；
  进程在事件被消费前退出，该事件不会自动重放。需要投递保证请用带 broker 的队列。

（口径与根 `README.md` 的「同类方案对比」表、`llms.txt` 的 *When not to use it* 一致。）

## 可直接投给上游文档的说明文字

见同目录 [`upstream-doc-snippet.md`](upstream-doc-snippet.md)。
