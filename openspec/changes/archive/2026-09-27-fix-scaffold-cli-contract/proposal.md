## Why

`zfc` 是外部用户接触本框架的第一道入口，但它的**输入边界没有契约**：非法标识符会静默产出一份 `SyntaxError` 的工程，`--create` 与 `--worker` 同时使用时 Worker 会落到刚创建的工程之外，目标目录已存在时静默 `exit 0`。

前序变更（`fix-scaffold-templates` / `fix-cross-platform-defects`）已经修好「生成的代码能不能跑」，本次修的是**命令接受什么输入、失败时如何表现**。已实测的复现证据：

| 输入 | 现状 | 期望 |
| --- | --- | --- |
| `--worker my-task` | `class My-TaskWorker`，`exit 0`，产物不可解析 | 拒绝并报错，不产出文件 |
| `--worker 123task` | `from workers.123task_worker import ...`，`exit 0` | 拒绝并报错 |
| `--create nested/app` | 裸 `FileNotFoundError` 栈 | 创建父目录或明确报错 |
| `--create X --worker Y` | `Y` 落在 `./workers/`，`X/src/main.py` 无注册 | `Y` 落进 `X/src/workers/` 并被注册 |
| `--create` 目标已存在 | 静默 `exit 0`，无输出 | 明确报错，不改动 |
| `--worker` 重复执行 | 入口重复追加导入行与注册条目 | 幂等 |

`templates/__init__.py` 的模块文档已经写下「模板产出的代码 MUST 直接可用」，而 `__main__.py` 至今没有任何输入校验——约束只写在文档里，没有落到可执行的断言上。

## What Changes

**A 组 · 输入合法性（P0）**

- **BREAKING** `zfc --worker <name>`：Worker 名 MUST 是合法 Python 标识符（非关键字、不以数字开头、不含连字符/空格）。非法输入 MUST 以非 0 退出码失败并指明原因，MUST NOT 产出任何文件。当前实现直接拼接 `.title()` 生成类名，无任何校验

**B 组 · 失败可见性（P1）**

- **BREAKING** `zfc --create <name>`：目标目录已存在时 MUST 明确报错并以非 0 退出码结束，MUST NOT 静默返回。当前 `create_func` 在 `os.path.exists` 为真时直接 `return`（`exit 0`），调用方无法区分「已创建」与「本来就存在」
- `zfc --create a/b`：MUST 支持嵌套路径，MUST NOT 向用户抛出裸 `FileNotFoundError` 栈。当前使用 `os.mkdir`，父目录不存在即抛栈

**C 组 · 组合语义（P1）**

- `zfc --create X --worker Y`：一次调用中，新 Worker MUST 落进本次创建的 `X` 内并被入口注册。当前 `worker_func` 从**进程 cwd** 反推产出目录，看不到同一次调用中刚创建的 `X`，于是把 `Y` 写到 `./workers/`，且 `X/src/main.py` 的 `WORKERS` 列表为空

**D 组 · 幂等（P2）**

- 对同一名称重复执行 `zfc --worker <name>` MUST NOT 在入口中重复追加导入行与注册条目。当前每次调用都无条件插入，入口随调用次数增长

**E 组 · 产出内容自洽（P2）**

- `src/conf/`、`src/params/`、`src/events/` 目前是三个**空占位包**，生成的代码从不引用它们，直接违反既有 capability `project-scaffolding` 的 requirement「MUST NOT 存在生成了但从不被加载的模块」。本次为三个目录各补一个**可加载的演示模块**，并让生成的入口真正导入它们：
  - `conf/` → `@configure(topic)` 配置函数，由 `Master.__init__` 的 `_load_config()` 执行
  - `params/` → `@params` 配置类，经 `ParamsFactory` 解析 `config.json`
  - `events/` → `@event(topic, channel)` 反应器，注册进 `EventChannelManager`
- 三个机制均已在本变更的调研中**实测生效**（见 design.md 的「已实测的机制契约」）

**F 组 · 文档与实现一致（P2）**

- `README.md` 记录的 CLI 选项 MUST 与实现一致。当前 `README.md` 示例给出 `zfc --thread demo`，而 `--thread` 不存在（实际报 `No such option '--thread'`，`exit 2`）

**测试**

- 上述每条各补一个回归用例：先在当前代码上复现为失败，修复后转绿。非法输入类用例 MUST 断言「未产出文件」，而不只断言退出码

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `cli-scaffolding`: 由「定位产出目录」扩展为**命令的输入与失败契约**——名称合法性校验、操作无法完成时的失败语义、`--create` 与 `--worker` 组合时的产出归属、重复调用的幂等性
- `project-scaffolding`: 新增「文档记录的 CLI 选项面 MUST 与实现一致」一项要求

> 说明一：`cli-scaffolding` 与 `project-scaffolding` 目前只以 `fix-scaffold-templates` / `fix-cross-platform-defects` 两个变更的 delta 存在于 `openspec/changes/`，尚未归档进 `openspec/specs/`。本次沿用同一 capability 路径，全部以 `ADDED Requirements` 增量表达，归档顺序无关。
>
> 说明二：**E 组（空占位包）不新增 requirement**。它违反的是 `project-scaffolding` 中既有的 requirement「脚手架产出的包结构 MUST 自洽 —— MUST NOT 存在生成了但从不被加载的模块」；前序变更只对该 requirement 的 `workers/` 部分做了验收，`conf/` / `params/` / `events/` 三个目录从未被断言覆盖。这是**验收缺口**而非需求缺口，因此按「不为满足校验而造需求」处理：补断言与产出，不动 spec 文本。

## Impact

- `zoo_framework/__main__.py`：输入校验、`--create` 失败语义与嵌套路径、`worker_func` 的目标目录改为显式传入、重复调用幂等
- `zoo_framework/templates/__init__.py`：新增 `conf` / `params` / `events` 三个演示模块模板；`main_template` 增加对三者的导入
- `README.md`：`--thread` 示例改为真实选项
- `tests/`：新增回归用例；`tests/test_scaffold_templates.py` 与 `tests/test_cross_platform_io.py` 中依赖「重复调用追加」或「目标已存在静默返回」的既有断言需同步改写
- **不受影响**：`resolve_worker_dir()` 在工作目录内的判定规则（由 `fix-cross-platform-defects` 交付）保持不变，本次只增加「显式指定目标目录」这一更高优先级的入口；`pyproject.toml` 依赖不变
