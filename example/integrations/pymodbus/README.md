# pymodbus 集成示例：进程内管理 Modbus 轮询与状态

## 演示什么

用 Zoo Framework 承载一个 Modbus 采集循环：常驻 Worker 按固定间隔轮询寄存器，把**最近读数**
与**越限次数**写入状态机并落盘，重启后从落盘值继续。它与 `native/reference/modbus_rtu.py`
里已实现的 Modbus 响应帧解析任务**同源**（都以 Modbus 作为真实设备 I/O 的载体），但这里走
**纯 Python** 路径，不依赖原生扩展。

为「复制即跑」，示例内置一个**模拟 Modbus TCP 设备**（`pymodbus` 的 `SimData`/`SimDevice`），
并有一个模拟线程通过写接口让温度循环变化，因此不需要真实硬件。

## 怎么跑

```bash
pip install "pymodbus>=3.16,<4"              # 不是 zoo-framework 的依赖
cd example/integrations/pymodbus             # 本目录（config.json 会被框架自动读取）
python poller.py                             # Ctrl-C 停止
```

## 期望输出

```
[register_poll_worker] poll #1 temp=26 pressure=1013 threshold breached (#1)
[register_poll_worker] poll #2 temp=26 pressure=1013 threshold breached (#2)
[register_poll_worker] poll #3 temp=28 pressure=1013 threshold breached (#3)
[register_poll_worker] poll #4 temp=22 pressure=1013
```

`poll #` 持续递增（状态落盘，重启后不归零）；温度越限时追加 `threshold breached (#K)`。

## 涉及哪些框架能力

- 常驻 Worker（`is_loop=True`）——按 `delay_time` 轮询的调度单元，替代手写 sleep-loop 线程。
- 状态机（`StateMachineManager`）——读/写读数与统计，原子落盘、重启恢复。
- 生命周期钩子（`_on_create` / `_destroy`）——在合适时机建立/释放 Modbus 连接。

## 何时不该用本框架

- **需要硬实时或亚秒级确定性控制** → 本框架的调度轮与 `delay_time` 以秒为量级，不适合做
  硬实时回路；请用专门的实时采集/PLC 侧逻辑。
- **任务需要跨机器 / 分布式** → 用 **Celery**。本框架没有跨机器调度。
- **需要 cron 表达式** → 用 **APScheduler**。本框架只有固定 `delay_time` 轮询。
- **需要多进程执行** → 本框架**未实现**，请求未实现的模式会被显式拒绝。
- **只做一次性读写** → 直接调用 `pymodbus` 客户端即可，不需要引入调度框架。

（口径与根 `README.md` 的「同类方案对比」表、`llms.txt` 的 *When not to use it* 一致。）

## 可直接投给上游文档的说明文字

见同目录 [`upstream-doc-snippet.md`](upstream-doc-snippet.md)。
