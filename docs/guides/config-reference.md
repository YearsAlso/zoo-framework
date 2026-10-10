# 配置参考

配置由 `Master()` 从工作目录的 `./config.json` 读取；用
`Master(MasterConfig(config_path="..."))` 可指定其它路径。**没有配置文件也能跑**（全部取默认值）。

键名使用 `段:键` 形式，与本文档的表格一一对应。默认值取自
`zoo_framework/params/*.py`。

---

## `worker` —— 调度与执行

| 键 | 默认 | 说明 |
|---|---|---|
| `worker:mode` | `""`（自动） | 执行模型：`thread` 或 `thread_pool`。留空时由 `worker:pool:enable` 推导 |
| `worker:runPolicy` | `"simple"` | 池的背压策略，见下表 |
| `worker:pool:size` | `5` | 线程池大小（`thread_pool` 模式下生效） |
| `worker:pool:enable` | `false` | 是否启用资源池（决定 `worker:mode` 的推导结果） |
| `worker:runTimeout` | `0` | 全局超时（秒）。`0` 表示不启用。见[超时与熔断](timeouts.md) |
| `worker:default:isLoop` | `false` | 未在 Worker 声明 `is_loop` 时的默认值 |
| `worker:default:delayTime` | `0` | 未在 Worker 声明 `delay_time` 时的默认值 |
| `worker:period` | `null` | 调度周期（秒）。`null` 表示按各 Worker 的 `delay_time` |
| `worker:phase` | `null` | 调度相位（秒），用于错开多个任务的执行时刻 |

### 背压策略 `worker:runPolicy`

只影响 `thread_pool` 模式下**池已满**时的行为：

| 值 | 池满时 | 适合 |
|---|---|---|
| `"simple"` | 扩容 | 突发流量、任务短 |
| `"stable"` | 排队 | 想限制并发但不丢任务 |
| `"safe"` | 拒绝 | 宁可跳过也不要积压 |

> 无法识别的取值会抛 `ValueError`（不静默降级）。

---

## `stateMachine` —— 状态持久化

| 键 | 默认 | 说明 |
|---|---|---|
| `stateMachine:picklePath` | `"./zooStates.pic"` | 状态文件路径 |
| `stateMachine:delay` | `5` | 落盘间隔（秒） |

状态还会在**优雅停机时**再存一次。落盘采用「先写 `.tmp` 再原子替换」，
并在同级 `backups/` 保留最近 5 份。

> **恢复语义是整表替换**，不是逐键合并。

---

## `event` —— 事件管道

| 键 | 默认 | 说明 |
|---|---|---|
| `event:delay` | `5` | 事件管道的检查节拍（秒） |
| `event:timeout` | `5` | 停机时等待事件管道排空的超时（秒） |
| `event:executor:workers` | `8` | 事件投递所用线程执行器的工作线程数 |
| `event:pushModelEnabled` | `false` | 推送模型：消费者挂在通道上等事件，入队即被叫醒（不再空转扫描） |
| `event:pushFallbackTimeout` | `1.0` | 推送模型的兜底等待上限（秒）。通道**逐个**等待，故总等待可达「通道数 × 该值」 |
| `event:dispatchBatchingEnabled` | `false` | 批量派发：同通道同响应器的一批事件合并为一次投递 |
| `event:batchMaxSize` | `64` | 批量派发的取件上限：每轮从**每个通道**最多取出的事件数（溢出者留队下一轮）。必须 ≥ 1 |

> **已移除**：`event:sleep`。它在 gevent 消费循环删除后成为零消费的死键，
> 填写它没有任何效果。请改用 `event:delay`。

---

## `log` —— 日志

| 键 | 默认 | 说明 |
|---|---|---|
| `log:path` | `"./logs"` | 日志目录，按日期分子目录 |
| `log:level` | `"info"` | 级别：`debug` / `info` / `warning` / `error` / `crit` |

**建议**：首次上手时把级别设为 `warning`，否则框架的调度日志会淹掉你自己的输出
（实测：5 秒运行默认 23 行，其中只有 3 行属于使用者）。

> 无法识别的级别会抛错，并列出支持的取值（不静默降级）。

---

## `native` —— 原生执行（Rust）

| 键 | 默认 | 说明 |
|---|---|---|
| `native:enabled` | `false` | 是否启用原生任务执行 |
| `native:contractVersion` | `0` | 期望的扩展契约版本；`0` 表示不校验 |

> **该扩展尚未发布到 PyPI**，因此当前打开它无法生效（见 issue #129）。

---

## `adaptive` —— 自适应调度

| 键 | 默认 | 说明 |
|---|---|---|
| `adaptive:enabled` | `false` | 是否启用双臂路由（按 Worker 类在线选择原生或 Python 执行） |
| `adaptive:exploration` | `0.05` | 探索率 |
| `adaptive:statsPath` | `""` | 统计数据落盘路径（空表示不落盘） |

---

## 完整示例

```json
{
  "log": { "path": "./logs", "level": "warning" },

  "worker": {
    "mode": "thread_pool",
    "runPolicy": "stable",
    "pool": { "size": 16, "enable": true },
    "runTimeout": 30
  },

  "stateMachine": {
    "picklePath": "./zooStates.pic",
    "delay": 10
  },

  "event": {
    "delay": 2,
    "executor": { "workers": 8 }
  }
}
```

## 配置的设计约定

两条贯穿全框架的约定，由测试保证：

1. **无法识别的取值会抛错，不会静默降级**——例如未知的 `runPolicy` 抛 `ValueError`，
   未知的日志级别抛错并列出支持的取值。
2. **配置与实现分离**：Worker 只能看到构造时传给它的 `props` 字典，
   不感知 `Waiter` / `WorkerRegistry` / `EventReactor` 的内部关系。
   因此新增一个 Worker 不需要读框架源码。
