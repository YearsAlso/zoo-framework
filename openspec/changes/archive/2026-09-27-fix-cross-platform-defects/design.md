## Context

动机与实测证据见 `proposal.md · Why`。此处只列影响方案选择的约束：

- **框架声明 `Operating System :: OS Independent`**，CI 的 `tests.yml` 覆盖 ubuntu / windows / macos 三平台，包发布到 PyPI。当前缺陷在单平台（开发者本机）不显现，但在跨平台使用时表现为静默数据损坏。
- **默认编码由 locale 决定**：Linux / macOS 默认 UTF-8，Windows 中文环境为 `cp936`（GBK）。实测 `locale.getpreferredencoding(False)` 返回 `cp936`。Python 3.13 的文本模式 `open()` 不指定 `encoding` 时即用该值。
- **全仓库 16 处文本模式 `open()` 未声明编码**，分布见 `proposal.md · Impact`。
- **日志内容含 emoji**（`utils/log_utils.py` 及各 Worker 的调用点），而 `conf/log_config.py:42` 的 `StreamHandler()` 未指定编码。
- **备份文件的消费方式依赖文件名排序**：`workers/state_machine_work.py:181,214,237` 与 `core/persistence_scheduler.py:223,259` 都用 `glob()` + `sort(reverse=True)` 取最新备份。**任何命名改动都必须保持"字典序等于时间序"**。
- **`zfc` 是 console script**，通过 `[project.scripts]` 暴露为 `zfc` 与 `zoo` 两个入口，因此在 Windows 上 `sys.argv[0]` 是 `.exe` 路径、在 Linux 上是 `/usr/local/bin/zfc`，二者都与源码目录结构无关。

## Goals / Non-Goals

**Goals:**

- 使同一份配置文件在所有平台上被解析为相同的值
- 使日志在非 UTF-8 控制台下最坏是字形降级，而不是整行消失
- 使备份文件的命名在任意调用频率下唯一，且保持既有的按名排序语义
- 使 `zfc --worker` 在任意平台把文件写进正确的目录
- 保证既有部署的可迁移性：不因本次变更而使已存在的配置文件突然不可读

**Non-Goals:**

- 不改变配置文件的格式（仍是 JSON），不做字符集自动嗅探
- 不引入平台专用依赖，不写平台分支封装
- 不修改 `utils/thread_safe_dict.py` 的锁实现（归 `fix-worker-scheduling`）
- 不把 `release.yml` 改为多平台（归 `adopt-rust-core-impl`）
- 不处理 `templates/__init__.py:34` 生成的 `Master(worker_count=5)` 与当前 API 不符的问题（同属脚手架产物正确性，但根因是 API 漂移而非平台判定，由 `fix-scaffold-templates` 处理）

## Decisions

### D1 · 文本 I/O 统一 UTF-8，读取路径带一次性可观测回退

**选择**：所有文本文件的**写入**一律显式 `encoding="utf-8"`；**读取**先按 UTF-8 解码，遇到 `UnicodeDecodeError` 时回退到 `locale.getpreferredencoding(False)`，并在回退发生时输出一条 WARNING，指明该文件应迁移为 UTF-8。

**理由**：写入侧必须唯一确定，否则损坏会持续产生。读取侧需要回退，是因为**已经存在旧版本在 Windows 上写出的 GBK 配置文件**（由 `params_factory.py:13` 的 `json.dump` 产生），直接硬读 UTF-8 会让这些用户的框架在启动路径上直接失败。用一条 WARNING 而非静默回退，是为了让技术债可见——这正是本变更要消灭的"静默损坏"模式的反面。

**已考虑的替代**：读取也硬编码 UTF-8。拒绝理由——失败点位于框架启动路径（`ParamsFactory.__init__`），代价过高，且本次修复不应把既有用户变成不可启动。

**已考虑的替代**：用 `errors="replace"` 让读取永不失败。拒绝理由——它把损坏静默化，读出的值看起来合理但实际是错的，与本变更要解决的缺陷同源。

### D2 · 日志：显式 UTF-8，且"不丢行"优先于"字形正确"

**选择**：控制台与流的日志 handler 显式声明 `encoding="utf-8"` 且 `errors="backslashreplace"`。

**理由**：日志的首要契约是**任何一条日志都不应整行消失**，字形正确是次要的。`backslashreplace` 保证任意码位都能被写出（最坏情况看到 `\U0001f4e6` 而非 emoji），从而保住行内容与时间戳。当前实现在 `cp936` 控制台上触发 `UnicodeEncodeError`，`logging` 的异常处理把整行丢弃，只在 stderr 留下一段 `--- Logging error ---` 与堆栈——**日志内容与它的时间戳一起丢失**，这比字形降级严重得多。

**已考虑的替代**：移除所有 emoji。拒绝理由——它改变了日志既有的可读性约定，且没有解决根本问题：非 ASCII 内容迟早还会出现（中文日志消息、用户数据），只是把触发条件推远。

**已考虑的替代**：`errors="replace"`。拒绝理由——`?` 无法还原原始码位，信息不可逆丢失；`backslashreplace` 保留了可还原性。

### D3 · 备份命名提升到微秒精度，保持字典序等于时间序

**选择**：`core/persistence_scheduler.py:180` 与 `workers/state_machine_work.py:150` 的时间戳格式由 `%Y%m%d_%H%M%S` 改为 `%Y%m%d_%H%M%S_%f`（6 位微秒）。

**理由**：既有的备份读取路径用 `glob()` + `sort(reverse=True)` 取最新（`state_machine_work.py:181,214,237`、`persistence_scheduler.py:223,259`），因此命名必须保持**字典序等于时间序**。固定宽度的微秒后缀满足该性质，且无需引入计数器。同一进程内两次备份的最小间隔是一次调度 tick，微秒精度远足够。

**已考虑的替代**：文件名加零填充序号（`_000001`）。拒绝理由——需要在每次备份时扫描目标目录计数，引入额外 I/O 与并发竞态，而 `%f` 已经解决唯一性问题。

**已考虑的替代**：使用 UUID。拒绝理由——破坏字典序排序，需要同步改动全部备份读取路径，且文件名不可读、不便于人工排查。

**备注**：两处实现的命名方案不同（`state_machine_*.pkl` 与 `<filename>.<timestamp>.bak`），本次只统一**时间戳精度**，不统一命名模板——模板差异属既有设计，不在本次范围内。

### D4 · CLI 目录定位改为依据工作目录结构，不依赖 `argv[0]`

**选择**：`zoo_framework/__main__.py` 的 `worker_func` 不再读取 `sys.argv[0]`，改为按当前工作目录的实际结构判定：

```
若 ./src 存在且为目录  →  产出到 ./src/workers
否则                   →  产出到 ./workers
```

**理由**：`create_func` 产出的脚手架布局是 `<project>/src/workers/`，因此在项目根执行时应有 `./src/workers`，在 `src/` 内执行时 `./src` 不存在、天然落到 `./workers`。这条规则完全由文件系统判定，覆盖两种真实用法且无需猜测进程是怎么被启动的。

当前判据 `sys.argv[0].endswith("/src")` 实测对 Windows 的 `C:\...\Scripts\zfc.exe`、`C:\proj\src\__main__.py` 与 Linux 的 `/usr/local/bin/zfc` **全部为假**——它不只是 Windows 失效，而是在所有平台上都是死条件。

**已考虑的替代**：新增 `--dir` 显式选项。拒绝理由——破坏现有 CLI 契约，且对本工具的主流用法（在项目根执行）是多余负担。

**已考虑的替代**：修正 `argv[0]` 的判断方式（如改判 `os.path.basename(os.getcwd()) == "src"`）。拒绝理由——仍然是从进程上下文猜测；**工作目录的结构**才是与产出位置直接相关的信息。

## Risks / Trade-offs

- **[读取回退被长期依赖，技术债固化]** → 回退分支必须输出 WARNING（含文件路径），使用例断言该告警存在；在文档中标注回退为过渡措施
- **[`errors="backslashreplace"` 让 emoji 在 Windows 控制台显示为转义序列，被误判为回归]** → 在提交说明与发布说明中明确这是**预期行为**：优先保证不丢行。同时确认日志文件同样以 UTF-8 写出，使文件中的 emoji 保持原样
- **[备份命名变更影响既有备份的发现]** → `glob` 模式 `state_machine_*.pkl` 与 `*.bak` 不变，新旧文件名可共存；排序仍按字典序 == 时间序，需新增用例断言新旧混排时"取最新"仍正确
- **[X1 的产出目录变化影响依赖旧行为的调用方]** → 已在 `proposal.md` 标注 BREAKING；变更需在发布说明中单列
- **[仅用 `skipif` 按平台跳过的测试可能掩盖问题]** → 编码类用例 MUST 可在**任意单平台**上复现（通过显式传入不同的编码模拟，而非依赖运行平台的 locale），避免"只有 Windows CI 才会红"

## Migration Plan

- **配置文件的迁移**：不提供自动迁移工具。读取回退保证旧文件可用并告警；用户在下次写入时自然得到 UTF-8 版本（`params_factory.py:13` 的写入路径仅在不存在的路径上触发，故新格式主要通过用户手工重建或后续版本的其他写入路径产生）
- **回滚策略**：本变更的四项互相独立，可分别回滚。X2 的回滚会重新引入静默损坏，X3/X4/X1 的回滚代价为恢复到已知缺陷状态
- **验证顺序**：X2（数据正确性，影响最大）→ X3（可观测性）→ X4（数据保留）→ X1（工具行为）

## Open Questions

### Open Question · 是否同时移除日志中的 emoji

**问题**：本变更选择保留 emoji 并修复编码（D2）。但 emoji 在以下场景仍有摩擦：非 UTF-8 的日志采集管道、某些终端字体、以及 grep 时的可读性。

**影响**：这是**产品表达偏好**而非技术约束——D2 的选择已经保证无论保留与否都不会丢行。该项不改变本变更的任何 Requirement、方案或任务拆解，因此可延后。

**状态**：不阻塞。若决定移除，应作为独立的、覆盖全部日志调用点的变更执行，而非在本变更中零散处理。
