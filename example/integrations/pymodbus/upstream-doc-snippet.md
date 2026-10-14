# 可直接投给上游文档的说明文字（pymodbus）

> 目标落点：pymodbus 文档的 Examples / 相关项目一节。原样可贴；措辞提交前须经维护者确认。

---

**进程内的采集循环与状态**

如果要做的是「按固定间隔轮询寄存器、把读数与统计保存下来」，可以把调度交给进程内的
[Zoo Framework](https://github.com/YearsAlso/zoo-framework)：常驻 Worker 负责轮询，状态机负责
把读数与统计原子落盘（重启后继续），不必自己写 sleep-loop 线程与持久化。它不做跨机器分发，
也不适合硬实时/亚秒级回路。

**何时不该用它**：需要硬实时的亚秒级确定性控制、需要跨机器或多进程（用 Celery）、
需要 cron 表达式（用 APScheduler），或只做一次性读写（直接用 pymodbus 客户端即可）。
