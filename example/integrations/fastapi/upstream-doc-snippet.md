# 可直接投给上游文档的说明文字（FastAPI / Starlette）

> 目标落点：上游文档的「Background Tasks / 集成」一节。3–5 行，原样可贴；措辞提交前须经维护者确认。

---

**进程内、无 broker 的后台任务**

`BackgroundTasks` 适合请求返回后的一次性收尾；若任务需要长期存活、保持进度、或在进程重启后继续，
可以嵌入 [Zoo Framework](https://github.com/YearsAlso/zoo-framework)：它在你自己的进程里提供调度、
事件管道与原子化的状态落盘，无需 Redis / RabbitMQ。它持久化的是**状态**而非待处理队列，也不做跨机器分发。

**何时不该用它**：任务需要跨机器或多进程（用 Celery）、需要 cron 表达式（用 APScheduler）、
或只需请求后的一次性回调（`BackgroundTasks` 已经够用）。
