## Context

动机见 `proposal.md · Why`，需求见 `specs/cli-scaffolding/spec.md` 与 `specs/project-scaffolding/spec.md`。以下是塑造方案的现状与约束。

`zoo_framework/__main__.py` 当前的结构：

```
zfc(create, worker)                 # 唯一的 click 命令，两个选项都是裸字符串
  +-- create_func(object_name)      # os.mkdir + json.dump(DEFAULT_CONF) + 写 5 个 __init__.py + 写 main.py
  +-- worker_func(worker_name)      # 从 cwd 反推产出目录；渲染模板；接线进 main.py
        +-- resolve_worker_dir()    # 依据 cwd 是否有 src/ 判定，由 fix-cross-platform-defects 交付
        +-- _worker_names(name)     # f"{name}_worker", f"{name.title()}Worker" —— 无校验
        +-- _wire_worker_into_main()# 以 marker 做 str.replace，无条件插入
```

约束：

- `create_func` 与 `worker_func` 是**公开的模块级函数**，既有测试直接调用它们，因此签名的变更要向后兼容。
- `resolve_worker_dir()` 的 cwd 判定规则由 `fix-cross-platform-defects` 交付并有独立验收，本次 MUST NOT 改动其语义。
- 模板是 `zoo_framework/templates/__init__.py` 里的模块级字符串，`main_template` 用 f-string 内嵌两个 marker 常量。
- 产出目录必须自带 `__init__.py`：`resolve_worker_dir` 会在产出目录不存在时补建，但补建逻辑只覆盖 `workers/`。

## Goals / Non-Goals

**Goals:**

- 命令的输入边界有可执行的契约：非法输入在**产出之前**失败，且失败可见（非 0 退出码 + 可读原因 + 不抛栈）。
- 产出归属明确：组合调用时新 Worker 落进本次创建的工程，而不是依赖进程 cwd 反推。
- 重复调用不累积产物。
- `conf/`、`params/`、`events/` 三个目录产出可被入口实际加载的内容，补齐既有 requirement「MUST NOT 存在生成了但从不被加载的模块」的验收。

**Non-Goals:**

- 不改 `resolve_worker_dir()` 的 cwd 判定规则（`fix-cross-platform-defects` 的验收面）。
- 不给 `zfc` 增加新选项（`--force` / `--dry-run` / `--target` 等均不在本次范围）。目标已存在时「不做合并、不做覆盖」是本次的明确选择。
- 不改框架运行时：`Master`、`EventChannelManager`、`ParamsFactory` 的行为一律不动。演示模块只能使用它们**当前实测可用**的机制。
- 不为已生成的坏项目提供迁移工具；用户手工修或重建。

## Decisions

### D1 · 名称校验用 `str.isidentifier()` + `keyword.iskeyword()`，拒绝而非规范化

校验点放在 `worker_func` 的**第一行**，早于任何文件读写。规则只有两条，都来自 Python 自身的标识符定义：

```
name.isidentifier() and not keyword.iskeyword(name)
```

`isidentifier()` 已覆盖「不以数字开头」「不含连字符/空白」「非空」；`keyword.iskeyword()` 补上 `class` / `def` 这类合法标识符但不可作类名的情况。

**为什么拒绝而不是规范化**（用户在三个选项中选定「拒绝并明确报错」）：规范化要新定义一整套规则——连字符、空格、点号、大小写、数字开头、关键字、以及与既有文件重名时如何取舍。这套规则本身就是新的验收面，而且静默改名会让用户按 `my-task` 找不到 `my_task_worker.py`。拒绝的代价只是惯性写法要改一次，收益是「命令接受什么」有唯一答案。

**备选**：就地 `re.sub(r'\W|^(?=\d)', '_', name)` 规范化后继续 —— 否决，理由是静默改名 + 规则不可枚举。

### D2 · 失败载体：参数取值非法用 `click.BadParameter`，运行期状态冲突用 `click.ClickException`

已实测两者的呈现（Click 8.x）：

| 异常 | 退出码 | 输出 |
| --- | --- | --- |
| `click.BadParameter` | 2 | `Usage: ...` + `Error: Invalid value: <msg>` |
| `click.ClickException` | 1 | `Error: <msg>` |

- 合法性问题（名称不是标识符）→ `click.BadParameter`，退出码 2。语义正是「这个参数的值不合法」，且 Click 会附带 usage。
- 状态冲突（`--create` 目标已存在）→ `click.ClickException`，退出码 1。目标已存在不是参数格式问题，附 usage 反而是噪音。
- 两者都由 Click 的 `main()` 捕获并统一呈现，**不会向用户抛栈**，直接满足「MUST NOT 暴露未捕获的异常栈」。

**备选**：抛 `FileExistsError` / `ValueError` —— 否决，会冒裸栈，正是 B 组要修的现象。

### D3 · 保持现场不变靠「先检查后动手」，不靠事后回滚

`create_func` 当前在 `os.path.exists` 为真时 `return`；改为 `raise click.ClickException(...)`，判断位置不变——仍在 `os.mkdir` 之前。因此「目标已存在时不改动现场」是该检查的**结构性保证**，不需要 try/except 回滚。

嵌套路径由 `os.mkdir` 换 `os.makedirs` 解决。两者独立：`makedirs` 默认 `exist_ok=False`，但目标已存在的情况已在更早处被拦截并给出更好的错误信息。

### D4 · 组合调用时把目标目录显式传给 `worker_func`，不改变进程 cwd

`worker_func` 增加一个**可选**参数，缺省时保持现有行为：

```
worker_func(worker_name, project_dir: str | None = None)
    project_dir is None -> src_dir = resolve_worker_dir()          # 既有行为，cwd 判定
    project_dir 给定     -> src_dir = <project_dir>/src/workers    # 组合调用
```

`zfc()` 在 `create` 成功后把 `create` 的值作为 `project_dir` 传入。既有测试直接调用 `worker_func("my_task")` 的地方不受影响。

**备选一**：`os.chdir()` 到新工程再调用 —— 否决。改变进程级 cwd 会在命令返回后污染调用方，且异常路径上还要回滚。
**备选二**：在 `create_func` 里写模块级变量给 `worker_func` 读 —— 否决，隐式跨调用状态，与「显式参数」相比没有收益。
**备选三**：让 `resolve_worker_dir()` 感知刚创建的目录 —— 否决，会把组合语义塞进一个单一职责的判定函数，且触及 `fix-cross-platform-defects` 的验收面。

### D5 · 接线幂等靠按行精确比较，不靠子串包含

`_wire_worker_into_main` 在插入前先判断入口是否已含该行：

- 导入行：与入口的各行 `strip()` 后精确相等才算已存在。
- 注册条目：同理，比较的是 `("MyTaskWorker", MyTaskWorker),` 整行。

**为什么按行而不是 `in content`**：与模板「一个 Worker 一行」的产出形态一致，且不会把更长的名字或注释里的片段误判为已存在。插入仍沿用 marker 定位，保持产出格式稳定。

**备选**：把 `WORKERS` 列表改成运行时扫描 `workers/` 目录自动生成 —— 否决。这会改变产出形态，让「入口显式注册」这一由 `fix-scaffold-templates` 确立并验收的契约失效，超出本次范围。

### D6 · 三个演示模块只用已实测的机制

三个机制均在本变更的调研中于临时目录**实测生效**，契约如下：

| 目录 | 机制 | 何时生效 | 回调/属性的实测形态 |
| --- | --- | --- | --- |
| `conf/` | `@configure(topic=...)` | 注册进 `config_funcs`，由 `Master.__init__` → `_load_config()` 调用（**无参**调用） | 函数体被执行，实测打印可见 |
| `params/` | `@params` + `ParamsPath` | 首次**导入**该模块时解析 | 类属性被替换为 `config.json` 中的值，实测取到 `demo:greeting` |
| `events/` | `@event(topic=..., channel=...)` | 导入时向 `EventChannelManager` 注册 `EventReactor` | `EventChannelManager().perform_event(EventNode(topic, content, channel))` 送达；回调收到**单个 `EventReactorReq`**，`.content` 才是载荷 |

两个必须写进模板的事实，写错就会产出「看着对但跑不通」的代码：

- `@configure` 注册的函数被**无参调用**（`master.py:234` 的 `value()`），因此演示函数 MUST NOT 声明必需参数。
- `@event` 的回调签名是**单个 `EventReactorReq`**，不是原始内容。实测时 `on_demo(content)` 收到的是 `EventReactorReq(topic=..., channel=..., reactor=..., priority=...)`。

示例模块只做声明与注册，**MUST NOT 在被导入时输出**。脚手架是起点不是演示程序，导入即打印会让用户第一次运行就看到不属于自己业务的输出。

### D7 · 空占位包补成演示模块，而不是删除

用户在三个选项中选定「补成可加载的演示模块」。理由：`project-scaffolding` 既有 requirement 已经要求「MUST NOT 存在生成了但从不被加载的模块」，删除与补齐都能满足；但 `conf/` / `params/` / `events/` 恰好对应框架三个真实扩展点，补齐同时把扩展点演示出来，用户不必读框架源码就知道往哪里放配置函数、配置类和事件反应器。

如 `proposal.md` 说明二所述，这一项**不新增 requirement** —— 它是对既有 requirement 的验收补齐。

## Risks / Trade-offs

- **[行为收紧：`--worker my-task` 从「能跑（产出坏代码）」变成「报错」]** → 在错误信息中直接给出合法写法示例；README 的示例统一使用下划线命名。
- **[`--create` 目标已存在从 `exit 0` 变成 `exit≠0`，可能打断脚本化的幂等调用]** → 这是用户明确选定的语义（「明确报错并不改动」）。README 需说明该行为，让脚本作者据此决定是否先判断存在性。
- **[演示模块引用框架内部机制，框架侧变更会让模板失效]** → 每个演示模块配一条「生成后真实导入并断言机制生效」的用例（`conf` 断言配置函数被调用、`params` 断言属性等于配置值、`events` 断言事件送达反应器）。模板失效时用例转红，而不是等到用户发现。
- **[生成的演示模块在被导入时写框架的进程级全局注册表]** → 三处全局状态跨用例存活：`sys.modules` 模块缓存、`config_funcs`（`core/aop/configure.py`）、`aop/params.py` 的 `config_params`。用例必须断言**本次导入的模块对象自己的副作用**（而不是"注册表里有这个名字"），并在 fixture 中把这三处一并清空。实施中已确认：只断言"注册表里有该 topic"会被上一个用例的残留蒙混过去，只有断言新模块对象的标志位才能暴露模板失效。
- **[`@params` 的解析缓存按裸类名索引，同名配置类在同一进程内相互覆盖]** → 实测：`aop/params.py:9-18` 以 `cls.__name__` 为键缓存已解析的类，因此两个同名类（例如两个脚手架项目各自的 `DemoParams`）在同一进程里，第二个会**直接返回第一个的类对象**，配置被静默替换成前一个项目的值。本变更的用例已在 fixture 中清掉该缓存条目以隔离；**缺陷本身不在本次范围**（属于框架的 `@params` 语义，不是 CLI 契约），登记为后续项。
- **[`main_template` 新增三个导入会改变既有测试的导入副作用]** → `tests/test_scaffold_templates.py` 与 `tests/test_cross_platform_io.py` 的 `scaffold` fixture 已清理 `sys.modules` 与 `sys.path`，但不清 `config_funcs`；相关用例需按上一条处理。
- **[`@params` 的解析依赖 cwd 下存在 `config.json`]** → 实测确认 `core/aop/params.py:26` 的 `_resolve` 以 `ParamsFactory()`（默认路径 `./config.json`）重新实例化，因此解析结果与 `Master` 的导入顺序无关，但**依赖 cwd**。脚手架项目的既定运行方式就是在项目根执行入口，与之一致。**不在本次范围**：`_resolve` 中这次重新实例化会以默认路径覆盖 `ParamsFactory.config_params`，当用户使用自定义配置文件路径时会读到错误的配置——这是独立的框架缺陷，登记为后续项。

## Migration Plan

- 破坏性变更两处：`--create` 对已存在目标由静默 `exit 0` 改为 `exit≠0`；`--worker` 对非法名称由「成功但产出坏代码」改为失败。二者均为对外 CLI 行为，需在提交信息正文中说明（仓库无 CHANGELOG，GitHub Release 正文由 `git log` 生成，与 `fix-scaffold-templates` 的既有做法一致）。
- 无数据迁移。已生成的坏工程由用户重建；脚手架产出物本身不参与版本管理。
- 回滚：改动集中在两个源文件加 README，`git revert` 单个提交即可。

## Open Questions

（无。三处设计分叉已由用户决策确认，其余均可由既有代码与实测确定。）
