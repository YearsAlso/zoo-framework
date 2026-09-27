## Context

动机与实测证据见 `proposal.md · Why`。此处只列影响方案选择的约束：

- **脚手架是纯字符串模板 + 目录写入**，没有运行时依赖。`templates/__init__.py` 定义三段 Jinja2 模板（`worker_template`、`main_template`、`worker_mod_insert_template`），`__main__.py` 负责渲染与落盘。改动面小、可验证性强。
- **`@worker` 装饰器写入的 `WorkerRegister` 没有任何消费者**。`core/aop/worker.py` 的 `worker_register` 是 `WorkerRegister` 实例；`Master` 用的是 `WorkerRegistry`（`core/worker_registry.py`）。两个注册体系并存，前者是死路径。且 `@worker` 在 import 期就实例化 Worker，早于配置加载。
- **`WorkerRegistry` 的装饰器路径同样不通**：`core/worker_registry.py:239-247` 的 `register_worker` 装饰器里 `isinstance(registry, WorkerRegistry)` 为假（`registry` 是 legacy 的 `WorkerRegister`），因此静默退化为 legacy 分支。因此**当前不存在任何能工作的 Worker 注册装饰器**。
- **`Master.register_worker(name, cls)` 是唯一有修复路径的注册 API**：`fix-worker-scheduling` 的任务 6.5 要求运行期注册的 Worker 进入调度。
- **`_destroy` 的生产调用点唯一**：`core/worker_registry.py:161-162` 的 `unregister`，而 `Master` 生命周期内无任何调用者。`fix-worker-scheduling` 的任务 6.2 要求停机触发销毁钩子。
- **产出的包结构不自洽**：实测 `src/` 下无 `__init__.py`，而 `conf/`、`events/`、`params/`、`workers/` 四个子目录都有。

## Goals / Non-Goals

**Goals:**

- 使 `zfc --create` + `zfc --worker` 产出的项目**可以被启动，且其中的 Worker 确实被执行**
- 使模板示范的 API 是**当前真实可用**的 API，而非历史遗留路径
- 使脚手架产出的配置被框架实际读取
- 使 CLI 的每个选项都有真实语义

**Non-Goals:**

- 不引入 Worker 目录自动发现机制
- 不重构或移除 `@worker` 装饰器与 `WorkerRegister` 旧注册体系——本变更只是不再示范它
- 不改产出目录的判定逻辑（`fix-cross-platform-defects` X1 承接）
- 不改 `worker:pool:enable` 的键名兼容实现（`fix-worker-scheduling` 5.1 承接）
- 不为脚手架增加配置项、模板自定义、多语言模板等新功能

## Decisions

### D1 · 以"生成的项目能被启动并执行 Worker"作为唯一验收契约

**选择**：本变更的所有要求都收敛到一条端到端路径上——生成 → 导入 → 启动 → 断言 Worker 被执行。不设"模板语法正确""文件已写入"这类中间指标作为验收物。

**理由**：当前缺陷的全部特征就是"每个中间环节看起来都对，但没有一条端到端路径能走通"。`worker_func` 确实写出了文件、`workers/__init__.py` 确实有导入行、`main.py` 确实是合法 Python——然而合起来跑不起来。用中间指标验收会重复这个错误。端到端用例是唯一能防止"局部正确、整体不通"的验收方式。

**已考虑的替代**：为每个缺陷设独立单元测试（模板字符串断言、CLI 参数断言）。拒绝理由——它们正是当前测试的形态：`tests/` 里没有任何脚手架用例，而既有用例全部通过。字符串断言无法发现 `Master(worker_count=5)` 这类"语法合法但 API 不存在"的问题。

### D2 · 注册改走 `Master.register_worker`，弃用 `@worker`

**选择**：模板产出使用 `Master.register_worker(name, cls)` 显式注册，移除 `@worker(count=1)` 与 `from zoo_framework import worker`。

**理由**：`@worker` 写入的 `WorkerRegister` 没有任何消费者，导入成功也不会被调度；而 `from zoo_framework import worker` 本身就会抛 `ImportError`（该名称不在包根）。`Master.register_worker` 是唯一在 `fix-worker-scheduling` 中被明确修复为"注册后进入调度"的路径（任务 6.5）。选择它意味着模板示范的 API 有明确的、已被承诺的行为。

**已考虑的替代**：保留 `@worker` 并修复它，使它注册进 `WorkerRegistry`。拒绝理由——`WorkerRegistry.register_worker` 装饰器当前在 import 期实例化 Worker（早于 `ParamsFactory` 读取配置），修复它需要改变公开装饰器的语义与时序，属独立的 API 设计议题，不应捆绑进脚手架修复。

**已考虑的替代**：引入 Worker 目录自动发现，让用户"把文件放进 `workers/` 就能用"。拒绝理由——这是功能增强而非缺陷修复，且需要定义契约（模块命名规则、类发现规则、加载时机与配置加载的先后）。在脚手架尚不能跑通时引入新机制，是在未验证的地基上加层。

### D3 · Worker 的加载路径显式化，并使产出包结构自洽

**选择**：产出的 `main.py` 显式导入 Worker 模块并注册；补全产出项目中缺失的 `src/__init__.py`，使包结构一致。

**理由**：实测 `worker_func` 把 `from .<name>_worker import <Name>Worker` 写进 `workers/__init__.py`，但没有任何代码导入 `workers` 包——这条导入语句是装饰性的。显式化之后，"生成的文件"与"被加载的代码"之间存在一条可追踪、可断言的链路。

**已考虑的替代**：仅在 `main.py` 里 `import workers`（依赖 `workers/__init__.py` 的导入行）。拒绝理由——它把"哪个 Worker 被启用"隐式地编码进包初始化文件，用户增删 Worker 时需要同时改两处；且在 `fix-cross-platform-defects` 的 X1 落地前，该文件可能位于错误目录。显式导入的失败模式更清晰。

### D4 · `zfc --config` 移除而非实现

**选择**：从 `__main__.py` 移除 `--config` 选项。

**理由**：该选项被 click 接受、在 `zfc` 函数体内出现 **0 次引用**，属静默忽略。一个被接受却什么都不做的选项，比一个不存在的选项更糟——用户执行 `zfc --config foo` 会认为自己的意图已被实现，而实际上没有产生任何效果。移除把"静默忽略"变为"明确报错未知选项"，这是更好的失败模式。

**已考虑的替代**：实现为"生成一个导出配置文件并写入 `config.json` 的 `_exports`"。该语义与现有的 `_exports` 机制自洽，是合理的功能候选——但它是一个**新功能**，当前没有已知用例，需求需先被确认。在缺陷修复中夹带猜测出来的新功能，会让变更的验收边界模糊。

**影响**：属 CLI 契约的 BREAKING。由于该选项此前不产生任何效果，移除不改变任何既有可用行为。

### D5 · 模板钩子名与框架实际调用的钩子对齐

**选择**：`worker_template` 给出的生命周期钩子名与框架在停机时实际调用的钩子名保持一致，并移除模板中框架不调用的钩子。

**理由**：模板当前给出 `_destroy(self, result)`，而 `_destroy` 唯一的生产调用点在 `WorkerRegistry.unregister`，`Master` 生命周期内无调用者。`fix-worker-scheduling` 的任务 6.2 要求停机触发销毁钩子，届时以哪个名字调用由该变更决定。本变更的责任是**名称一致**，避免模板与框架长期各说各话——这正是 `is_loop`、`stop()`、`_destroy` 这一类"文档承诺与实现不符"问题的同一个模式。

## Risks / Trade-offs

- **[对 `fix-worker-scheduling` 的硬依赖未满足，导致本变更的端到端用例无法转绿]** → 依赖已逐项列在 `proposal.md · Impact`；`tasks.md` 第 1 组把依赖确认设为门禁。若该变更的 6.5 未落地，S2 的用例会红——这是**正确的信号**，不应通过放宽断言来绕过
- **[模板变更后，已用旧版脚手架生成的项目不会自动更新]** → 变更需在发布说明中给出新旧产物对照；不在代码中做兼容（脚手架的产物是用户资产，框架不应改写）
- **[移除 `--config` 可能并非用户期望]** → 已在 D4 记录替代方案（实现为 `_exports` 的导出配置生成器）；若确认需要该功能，应作为独立变更按需求设计
- **[端到端用例依赖真实文件系统与进程启动，可能变慢或脆弱]** → 用例在临时目录内运行，不依赖真实项目结构；调用 `create_func`/`worker_func` 而非子进程执行 CLI；启动验证通过导入 `main` 模块并调用其入口函数完成，不真正进入 `master.run()` 的无限循环
- **[`src/__init__.py` 的补全可能改变既有产物的导入语义]** → 该文件此前不存在，补全是新增而非修改；需在用例中确认 `main.py` 与 `workers/` 的导入路径均不受影响

## Migration Plan

- **不迁移已有脚手架产物**。脚手架产出的是用户资产，框架不提供原地升级。发布说明给出新旧对照，由用户按需重生成
- **回滚策略**：模板为纯字符串常量，任一项可独立回滚。`--config` 的回滚恢复一个已知无效果的选项
- **验证顺序**：S1（导入）→ S3（入口可运行）→ S2（Worker 被调度）→ S6（加载路径与包结构）→ S4（配置生效）→ S7（钩子名）→ S5（CLI 选项）
  该顺序按"能否形成端到端链路"排列：前四项合起来构成 D1 的可验收契约，后三项是各自独立的正确性要求

## Open Questions

### Open Question · 是否复活装饰器注册或引入目录自动发现

**问题**：`@worker` 与 `WorkerRegistry` 的装饰器路径当前都不通（见 Context）。本变更选择绕开它们、改用显式注册。但"写个类加个装饰器就能用"显然是更符合框架定位的体验。

**影响**：这是**功能设计**问题，不是本次修复的约束。它不改变本变更的任何 Requirement、方案或任务拆解——无论将来是否复活装饰器，脚手架都必须先能跑通显式注册这条路径。

**状态**：不阻塞。若决定做，需要先定三件事：装饰器注册的时序（如何晚于配置加载）、`WorkerRegister` 与 `WorkerRegistry` 两套体系如何收敛、以及自动发现的契约定。这三项都超出脚手架缺陷修复的范围。
