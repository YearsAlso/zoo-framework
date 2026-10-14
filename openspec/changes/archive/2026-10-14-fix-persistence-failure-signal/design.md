## Context

`PersistenceScheduler.save` 的失败分支只做两件事：`LogUtils.error("❌ Failed to save data")` 与
`return False`。`PicklePersistenceStrategy.save` 更早一步把底层 `OSError`（父目录缺失即
`FileNotFoundError`）吞成一条 ERROR 日志 + `False`。调用方（`stop()`、`update_data(auto_save=True)`、
后台线程、使用方代码）普遍忽略返回值，于是"父目录不存在"这种**必然且持续**的失败在日志之外完全
不可见，`_dirty` 永远为真、每次 tick 反复失败。

## Decision

把失败变成调用方无法忽略的信号，分两处落地：

1. **启动校验（fail-fast）**：`ensure_storage_ready()` 检查目标目录存在且可写，`start()` 首先
   调用它。配置错误在启动那一刻暴露，而不是靠日志。
2. **落盘显式报错**：`save()` 在策略返回 `False` 时抛 `PersistenceError`（携带目标路径与"看上一
   条日志取原因"的指引），并保持 `_dirty` 为真以便重试。保留两种**非失败**的返回：成功时 `True`；
   无数据可落盘（`_data is None`）时 `False`——它表示"无事可做"，不是失败。

引入专用异常类型而非复用内建 `RuntimeError`：调用方可精确捕获持久化失败，与其它运行时错误区分。

### 为什么不自动建目录

自动 `makedirs` 也能消除该失败，但那会把"配置写错路径"悄悄改写成"框架替你建了一串目录"，属于未被
请求的自动修复；本 issue 要的是**显式化**。是否为便利性追加自动建目录留作待裁决项。

### 读盘与写盘语义不同

`load()` 在文件缺失时优雅返回空值（首次启动没有存档是正常态），本变更 MUST NOT 改变它；只有**写盘
不可完成**才抛错。

## Non-goals

- 不改 `load()` 的优雅语义（缺失文件 → 空值）。
- 不改备份 / 校验和 / 原子替换（`.tmp` + `os.replace`）的既有行为。
- 不改 `StateMachineWorker`（`zoo_framework/workers/`）自身的落盘实现。
- 不改后台线程 `_scheduler_loop` 的"记录后继续"策略：终止线程会让持久化静默停摆，比逐拍记录更糟；
  该场景（运行中目录被删）由 `start()` 的前置校验覆盖其常见形态，残留形态列为待裁决项。

## Language

中文注释 / 文档；docstring 保持 Google 风格（`Args:` / `Returns:` / `Raises:`）。
