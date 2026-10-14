# 可直接投给上游文档的说明文字（MCP Python SDK / 服务器示例）

> 目标落点：MCP server 文档/示例中「长耗时工具 / 后台执行」相关一节。原样可贴；措辞提交前须经维护者确认。
> 具体面向哪一份文档或示例仓（官方 `modelcontextprotocol` 文档还是某个 server 示例仓）留待维护者确认。

---

**长耗时的工具调用**

如果某个工具要长时间运行，不要直接 `await`——那会阻塞 server。可以把工作交给进程内的
[Zoo Framework](https://github.com/YearsAlso/zoo-framework)：工具投递任务后立即返回，常驻 Worker
在后台线程处理，进度写入状态机并可跨进程重启保留。它不做跨机器分发，持久化的是状态而非任务队列。

**何时不该用它**：任务需要跨机器或多进程（用 Celery）、需要 cron 表达式（用 APScheduler），
或工具本就是瞬时同步调用（直接返回即可）。
