# 技术设计：quiet-default-logs

## 实测基线

- 控制台日志走 **stderr**（`SafeStreamHandler` 继承 `logging.StreamHandler` 默认流），
  10 秒 scaffold 运行 stdout+stderr 共 22 行（默认 config 级别 debug）；
- `record_execute()` 在框架内**零调用点**——`_metrics` 只在 `register_worker`
  初始化为全 0 后从不更新，`get_worker_health` 恒回 `execute_count: 0`，
  "monitoring started" 与读 API 事实矛盾坐实；
- `base_worker.run()` 的 Start/Stop 走 `LogUtils.info`，其余系统 Worker 内部还有
  `state_machine_work.py` 的 `✅ State machines loaded: N states`（低频，info）。

## 决策

### D1: Start/Stop 降为 debug——按日志语义而不是按 Worker 名单降

改 `base_worker.run()` 的两行 `LogUtils.info` → `LogUtils.debug`，而不是在
`EventWorker` / `StateMachineWorker` 子类里覆盖降级。理由：这两行的语义就是
"单次执行的进入/退出心跳"，**任何** Worker 都不是用户要看的默认输出（#110 的
`scaffold` demo 也走了 `print` 而非日志，语义一致——用户业务输出不该走日志通道）。
按语义改一处覆盖全部 Worker，未来新增 Worker 不会重新犯同样的错。

### D2: SVM 日志——选方案 b（改写为如实表述 + debug），不删除

理由：`SVMWorker` 的**监控线程本身是真实存在且在跑的**（`_monitor_loop` 每
`_check_interval` 检查一次速率并翻转 `status`），消失的只是"指标输入"这一段。
方案 a（整段删除）会让"监控线程已启动"这一真实事件也失去日志踪迹，调试停机
顺序时无处回溯；方案 b 保留事件轨迹并把"未实现"如实写出来，与 README 特性表的
`⚠️ Metric pipeline not yet wired` 同一事实口径。改写要点：

- `registered to SVM` → `SVM worker registered (metrics input not wired;
  get_health_report() returns zeros)`，debug；
- `SVM monitoring started` / `SVM Worker setup completed` → 合并为一条如实表述
  `SVM monitor thread started (metrics input not wired; health report stays zero)`；
  `setup completed` 这条本身是纯仪式性（紧跟 start 后一行），直降 debug 并改写；
- `unregistered from SVM` / `monitoring stopped` 是停机路径的低频日志，仅改如实
  措辞、保持原本级别（不扩大改动面）。

### D3: 脚手架 config 默认级别 warning 而不是 info

`warning` 下启动横幅（`🎪 Master started`）、注册类 info 日志全部静默，
业务与异常仍可见；`info` 只挡住 Start/Stop，挡不住注册噪声（scaffold 一次
启动约 10 行 info）。诊断路径不变：`config.json` 的 `log.level` 改回去。
注意 `log_config_instance` 对**非法**级别字符串依旧显式抛错——默认值变更
不触碰该校验。

### D4: 文件日志不受影响

`FileHandler` 挂在 root logger 上、无独立 level（跟随 logger 级别）。降级后
默认级别 `warning` 下文件里也不再有 Start/Stop——这是预期行为（文件跟控制台
同一真相），需要细粒度历史的人把 `log.level` 设为 `debug` 即可，两通道同开关，
无双通道不一致的新问题。

### D5: 测试钉契约而不是钉文案

- 用 caplog / 级别断言"默认 root level 下 Start/Stop 不再产生可输出记录"，不
  断言完整文案（时间戳/颜色格式无关）；文案层只断"SVM 日志不含
  `SVM monitoring started` 这一具体断言性措辞"（issue 验收 grep 同名）；
- 脚手架 config 断言 `json.load(DEFAULT_CONF)` 的 `log.level == "warning"`；
  同时断言非法级别仍被拒绝（既有 vocabulary 校验路径不回归）。

## 实查清单：其余"断言未实现能力"的日志/字符串（只列不改）

逐个核查过 `grep -rn` 断言性日志：

1. `core/persistence_scheduler.py` 的 `✅ Persistence scheduler started` /
   `Restored from backup` —— 持久化**真实发生**（有实现有调用），不断言未实现
   能力，不动；
2. `constant/waiter_constant.py` / `constant/worker_constant.py` 的 process /
   coroutine 占位常量 —— 全部配显式 `NotImplementedError` 拒绝路径
   （`base_waiter.py`），没有"假装成功"的日志，不动；
3. `state_machine_work.py` `✅ State machines loaded: N states` —— 加载真实
   发生（N=0 时如实说 0），低频，不动；
4. `reactor/event_reactor_manager.py` `✅ Reactor 'X' registered to channels` ——
   注册真实发生，不动。

结论：断言性但**不实**的日志只有 SVM 三处，无顺手扩散面。

## 风险

- CLI 测试里 `test_documented_examples_run_successfully` 等会真实跑入口——降级后
  stderr 变瘦，无断言依赖这些日志（已核查）；预期全量绿。
- 开发者习惯在文件日志里找 Start/Stop 的：D4 已述，`log.level` 显式打开。
