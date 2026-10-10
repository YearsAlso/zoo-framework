# 05 · 使用脚手架

**目标**：用 `zfc` 生成一个带目录结构的项目，并理解它产出了什么。

前几篇都是从单个 `main.py` 开始。真实项目需要目录结构——
`conf/`（启动期配置钩子）、`params/`（配置项声明）、`events/`（事件反应器）、`workers/`（任务）。

## 1. 生成项目

```bash
zfc --create myapp
cd myapp
```

**产出的结构**：

```
myapp/
├── config.json
└── src/
    ├── main.py          # 入口：注册 Worker 并启动
    ├── conf/demo_conf.py       # 启动期配置钩子
    ├── params/demo_params.py   # 配置项声明（对应 config.json 的 demo 段）
    ├── events/demo_event.py    # 事件反应器示例
    └── workers/__init__.py
```

## 2. 加一个任务

```bash
zfc --worker order_sync
```

它做两件事：写 `src/workers/order_sync_worker.py`，**并把 import 与注册写进 `src/main.py`**。

打开 `src/main.py` 确认接线：

```python
# doc-example: skip —— 本块是**脚手架产物内部**的代码，
# 其导入路径相对于生成的 src/，无法在文档上下文里独立执行
from workers.order_sync_worker import Order_SyncWorker
# zfc:worker-imports

WORKERS = [
    ("Order_SyncWorker", Order_SyncWorker),
    # zfc:worker-registrations
]
```

> **已知问题（issue #112）**：`--worker order_sync` 目前生成的类名是
> `Order_SyncWorker`（下划线被保留），而不是 `OrderSyncWorker`。
> 功能正常，但命名不理想，修复在跟踪中。

## 3. 运行

```bash
python -u src/main.py
```

**注意**：脚手架默认把日志级别设为 `debug`，输出会比较吵。
建议先把 `config.json` 的 `log.level` 改成 `warning`：

```json
{ "log": { "path": "./logs", "level": "warning" } }
```

## 4. 理解生成的四类文件

| 目录 | 职责 | 何时用 |
|---|---|---|
| `conf/` | **启动期**配置钩子，在 `Master()` 构造时执行 | 需要在调度开始前做一次性准备 |
| `params/` | 把 `config.json` 的值解析成参数类 | 想让配置有默认值、校验与类型 |
| `events/` | 事件反应器 | 任务之间要通信 |
| `workers/` | 任务单元 | 你的业务逻辑 |

**导入时机有约束**（脚手架生成的 `main.py` 里已注明）：

```
conf   —— 注册配置钩子，必须早于 Master()：钩子在 Master 构造时执行
params —— 解析 config.json，须在配置载入之后
events —— 注册事件反应器
```

## 5. 已知问题

| 问题 | 状态 |
|---|---|
| `--create` 成功后不打印任何提示（没有"下一步运行什么"） | issue #110 |
| `--worker <name>` 的类名保留下划线（`Order_SyncWorker`） | issue #112 |
| 脚手架默认 `log.level` 是 `debug`，输出较吵 | issue #111 |
| 生成的 `WORKERS` 列表初始为空——**不跑 `--worker` 就看不到任何业务输出** | issue #110 |

> 最后一个尤其值得注意：**`zfc --create` 不会给你一个会打印东西的示例 Worker。**
> 想立刻看到输出，请先执行一次 `zfc --worker <name>`，
> 或直接照[第一篇](01-quickstart.md)手写一个。

## 常见错误

### `zfc: command not found`

包没装到当前解释器。用 `python -m pip install zoo-framework`，
或直接 `python -m zoo_framework`。

### 加了 Worker 但没被调度

检查 `src/main.py` 的 `WORKERS` 列表里是否有它。
`--worker` 应该自动接线；若你手工创建了文件，需要自己加 import 与注册项。

### 换了目录再运行，报找不到 config.json

`Master()` 默认读**当前工作目录**的 `./config.json`。
从项目根目录运行，或用 `Master(MasterConfig(config_path="..."))` 指定路径。

## 下一步

- [指南](../guides/README.md) —— 按"我要做 X"查
- [配置参考](../guides/config-reference.md) —— 全部配置键
- [API 参考](../api/README.md) —— 签名与参数
