## Why

`zfc --create` 产出的项目**在每一步都是断的**——生成的文件无法导入、生成的入口无法运行、生成的配置不被读取。实测一次完整生成（临时目录内执行 `create_func('demoapp')` + `worker_func('my_task')`）：

```
生成的 workers/my_task_worker.py
  → 导入失败: ImportError: cannot import name 'worker' from 'zoo_framework'
生成的 src/main.py
  → Master(worker_count=5) -> TypeError: unexpected keyword argument 'worker_count'
生成的 config.json
  → "pool": {"enabled": false}   而代码读的是 worker:pool:enable
CLI
  → --config 选项在 zfc 函数体内出现 0 次引用
```

四个独立的断点，覆盖脚手架的全部产物。用户按文档执行第一次命令就会撞上，且每一处都需要读框架源码才能定位。

在此基础上还有两处更深的问题：

- **生成的 Worker 模块没有任何加载路径**。`worker_func` 把 `from .<name>_worker import <Name>Worker` 写进 `workers/__init__.py`，但产出的 `main.py` 从不导入 `workers` 包，框架也没有目录扫描机制——即使用户实现了 Worker，它也不会被加载。
- **模板教用户实现一个框架从不调用的钩子**。`worker_template` 给出 `_destroy(self, result)`，而 `_destroy` 唯一的生产调用点在 `WorkerRegistry.unregister`，该方法在 `Master` 的生命周期内没有任何调用者（`Master.shutdown()` 目前只停 SVM）。

根因是模板示范的是一套**从未被接通**的 API：`@worker` 装饰器把实例写进 `WorkerRegister`，而该注册表没有任何消费者（`Master` 用的是 `WorkerRegistry`）。这不是模板写错了几行，而是模板在教一条不存在的路径。

`zoo-framework` 已发布到 PyPI，脚手架是用户接触框架的第一个入口，必须可用。

## What Changes

**S1 · 生成的 Worker 文件 MUST 可被导入**

- `zoo_framework/templates/__init__.py` 的 `worker_template` 移除 `from zoo_framework import worker`（该名称在包根不存在，实测抛 `ImportError`）

**S2 · 生成的 Worker MUST 被调度**

- **BREAKING**（产物）模板弃用 `@worker(count=1)`，改用 `Master.register_worker(name, cls)`。`@worker` 写入的 `WorkerRegister` 无任何消费者，即使导入成功 Worker 也不会运行
- 依赖 `fix-worker-scheduling` 的任务 6.5（运行期注册的 Worker 进入调度）——该依赖未满足时本项无法成立

**S3 · 生成的入口 MUST 可运行**

- `main_template` 修正 `Master(worker_count=5)`（实测抛 `TypeError`）为当前 `Master` 的公开构造方式

**S4 · 生成的配置 MUST 被框架实际读取**

- 该项的**修复**由 `fix-worker-scheduling` 的任务 5.1 承接（`worker:pool:enabled` 与 `worker:pool:enable` 的键名兼容）；本变更只补一条端到端用例守住"脚手架产出的配置确实生效"，不重复修复

**S5 · CLI 选项 MUST 生效，MUST NOT 被静默忽略**

- **BREAKING**（CLI 契约）移除 `zfc --config`：该选项被 click 接受、在 `zfc` 函数体内 0 次引用，属静默忽略。一个被接受却什么都不做的选项，比一个不存在的选项更糟——它让用户以为自己的意图已被实现
- **实现已由 `fix-cross-platform-defects` 交付**：该变更在修 X1（产出目录定位）时同处 `__main__.py` 的 `zfc` 命令定义，一并移除了该选项。本变更只需复核其行为并补断言，不重复实现。这与 S4（配置键名由 `fix-worker-scheduling` 承接）是同一种处理方式

**S6 · 生成的 Worker 模块 MUST 有明确的加载路径**

- 产出的 `main.py` 显式导入并使用 Worker，使"生成的文件"与"被加载的代码"之间存在可追踪的链路
- 补全产出项目中缺失的包结构（实测 `src/` 下无 `__init__.py`，而其全部子目录都有）

**S7 · 模板给出的生命周期钩子 MUST 与框架实际调用的钩子一致**

- 模板中的钩子名与框架在停机时实际调用的钩子名保持一致
- 依赖 `fix-worker-scheduling` 的任务 6.2（停机触发 Worker 销毁钩子）——该依赖未满足时钩子仍不会被调用，本变更只保证**名称一致**，不负责接线

## Capabilities

### New Capabilities

- `project-scaffolding`:脚手架产出内容的正确性——生成的项目可启动、生成的 Worker 可被导入并被调度、生成的配置可被框架读取、CLI 选项具备真实语义、产出包结构自洽

### Modified Capabilities

无。本能力为新建，不改变 `openspec/specs/` 下既有四个能力的任何 Requirement。

**与 `fix-cross-platform-defects` 的 `cli-scaffolding` 能力的边界**：该能力管**产出位置**的正确性（文件落在哪个目录），本能力管**产出内容**的正确性（生成的东西能不能跑）。两者互补，共同决定"脚手架可用"，但相互独立、可分别验收。

## Impact

| 类别 | 文件 |
|---|---|
| 模板 | `zoo_framework/templates/__init__.py`（`worker_template`、`main_template`、`worker_mod_insert_template`） |
| CLI | `zoo_framework/__main__.py`（`create_func` 的包结构、`zfc` 的选项定义） |
| 测试 | 新增脚手架端到端用例：生成 → 导入 → 启动 → 断言 Worker 被执行 |

**依赖**

| 依赖项 | 承接变更 | 未满足时的后果 |
|---|---|---|
| 运行期注册的 Worker 进入调度 | `fix-worker-scheduling` 6.5 | S2 无法成立——改用 `Master.register_worker` 后依然不会被调度 |
| 停机触发销毁钩子 | `fix-worker-scheduling` 6.2 | S7 只能保证名称一致，钩子仍不被调用 |
| 产出目录定位 | `fix-cross-platform-defects` X1 | 端到端用例需自行指定目录，但不阻塞本变更的修复 |

**不涉及的边界**

- **不改产出目录的判定逻辑**（`fix-cross-platform-defects` X1 承接）
- **不改 `worker:pool:enable` 的键名兼容**（`fix-worker-scheduling` 5.1 承接）
- **不重构 `@worker` 装饰器 / `WorkerRegister` 旧注册体系**：本变更只是不再示范它。这两个体系的去留属独立议题，涉及公开 API 的移除，应由专门变更处理
- **不引入 Worker 目录自动发现机制**：产出的 `main.py` 显式注册是当前最易验证的路径；自动发现是功能增强而非缺陷修复
- 不改变 `zfc` 已有的 `--create` / `--worker` 两个选项的名字与语义

**BREAKING 说明**

- 模板产出的 `main.py` 与 `*_worker.py` 内容变化，已用旧版脚手架生成的项目不会自动更新。变更需在发布说明中给出新旧产物的对照
- `zfc --config` 被移除。由于它此前不产生任何效果，移除不改变既有可用行为，只把"静默忽略"变为"明确报错未知选项"
