## Why

框架的文本 I/O 依赖平台 locale 编码，导致**同一份配置文件在不同平台上解析出不同的值，且不报错**。实测（Windows 11 中文环境，`locale.getpreferredencoding(False)` = `cp936`）：

```
UTF-8 文件内容: {"log": {"level": "调试"}}
未指定编码读取: {'log': {'level': '璋冭瘯'}}     ← 无异常，值被静默改掉
未指定编码写入: b'{"desc": "\xd6\xd0\xce\xc4\xc3\xe8\xca\xf6"}'   ← GBK 字节
```

Linux 与 macOS 的 locale 默认是 UTF-8，Windows 中文环境是 GBK。同一份 `config.json` 在两端读出的值不同，且 Windows 侧不抛异常——**这是数据损坏而非崩溃，排查成本极高**。全仓库有 16 处文本模式 `open()` 未声明编码。

同类问题还有两处已实测确认的缺陷：

- **日志在非 UTF-8 控制台整体丢失**：日志内容含 emoji，Windows 中文控制台触发 `UnicodeEncodeError`，`logging` 模块的异常处理让整行日志消失，只在 stderr 留下 `--- Logging error ---`。
- **备份文件在同一秒内相互覆盖**：备份名用 `%Y%m%d_%H%M%S`，实测连续 3 次备份只产出 1 个文件。

以及一处 CLI 缺陷：

- **`zfc --worker` 在任意平台都定位不到 `src/` 目录**：判据是 `sys.argv[0].endswith("/src")`，实测对 Windows 的 `C:\...\Scripts\zfc.exe`、`C:\proj\src\__main__.py`，以及 Linux 的 `/usr/local/bin/zfc` **全部为假**，只有 `sys.argv[0]` 字面等于某个以 `/src` 结尾的路径时才为真——实际中不会发生。因此该分支是死代码，`--worker` 永远写入 `./workers`。

这些缺陷在单平台开发时不显现，但框架声明 `Operating System :: OS Independent` 且 CI 覆盖三平台、发布到 PyPI，属必须修复的契约不一致。

## What Changes

**X1 · CLI 脚手架 MUST 在任意平台定位正确目录**

- **BREAKING**（行为）`zoo_framework/__main__.py:65`：`sys.argv[0].endswith("/src")` 改为依据当前工作目录的实际结构判定，不再从 `argv[0]` 猜测

**X2 · 文本文件读写 MUST 显式声明编码**

- `zoo_framework/core/params_factory.py:13,16,41`：配置文件的读写显式使用 UTF-8（**这是影响最大的一处**——它决定用户配置能否被正确解析）
- `zoo_framework/core/persistence_scheduler.py:131,148`：校验和文件
- `zoo_framework/utils/file_utils.py:61`、`zoo_framework/__main__.py` 的 9 处脚手架文件写入
- 读取路径对既有非 UTF-8 文件提供一次可观测的兼容回退，MUST NOT 静默损坏

**X3 · 日志 MUST NOT 因控制台编码而整体丢失**

- `zoo_framework/conf/log_config.py:42` 的控制台 handler 与 `zoo_framework/utils/structured_log.py:84` 的流输出显式声明编码
- 目标：非 UTF-8 控制台下最坏情况是字形降级，MUST NOT 是整行日志消失

**X4 · 备份文件名 MUST 在同一秒内保持唯一**

- `zoo_framework/core/persistence_scheduler.py:180`、`zoo_framework/workers/state_machine_work.py:150` 的时间戳精度提升
- 命名 MUST 保持"字典序等于时间序"，因为既有代码用 `glob()` + `sort(reverse=True)` 取最新备份

## Capabilities

### New Capabilities

- `cross-platform-io`:文本文件的读写编码契约、日志输出在非 UTF-8 控制台下的可用性、以及备份文件命名的唯一性与可排序性
- `cli-scaffolding`:`zfc` 命令行工具在任意平台上定位产出目录的正确性

### Modified Capabilities

无。本次两个能力均为新建，且不改变 `openspec/specs/` 下既有四个能力的任何 Requirement。

## Impact

| 类别 | 文件 |
|---|---|
| CLI | `zoo_framework/__main__.py` |
| 配置读写 | `zoo_framework/core/params_factory.py` |
| 持久化 | `zoo_framework/core/persistence_scheduler.py`、`zoo_framework/workers/state_machine_work.py` |
| 日志 | `zoo_framework/conf/log_config.py`、`zoo_framework/utils/structured_log.py` |
| 工具 | `zoo_framework/utils/file_utils.py` |
| 测试 | 新增跨平台行为用例；三平台 CI 矩阵（`tests.yml`）应能验证 |

**不涉及的边界**

- **不改 `zoo_framework/utils/thread_safe_dict.py`**：其 `multiprocessing.Lock` 问题（Windows 2063 ns vs Linux 181 ns）已由 `fix-worker-scheduling` 的纯 Python 优化承接，此处不重复登记
- **不改 `.github/workflows/release.yml` 为多平台**：该项属 `adopt-rust-core-impl`（P3）的必办项，在纯 Python 阶段无害
- 不引入任何平台专用依赖（`pywin32` / `colorama` 等），不写平台分支封装
- 不改变配置文件的**格式**（仍是 JSON），只改变其**编码**；不做字符集自动嗅探
- 不处理 `zoo_framework/templates/__init__.py:34` 生成的 `Master(worker_count=5)` 与当前 API 不符的问题——它同属 CLI 脚手架的产物正确性，但根因是 API 漂移而非平台判定，由 `fix-scaffold-templates` 承接。两者的能力边界：本变更的 `cli-scaffolding` 管**产出位置**，该变更的 `project-scaffolding` 管**产出内容**
- 与 `adopt-rust-core` 无依赖关系：本变更修的是 Python 层缺陷，该变更只做测量与决策，二者可并行

**BREAKING 说明**

- X1 改变 `zfc --worker` 的产出目录（从错误的 `./workers` 变为依据实际结构的正确目录）。依赖旧行为、且工作目录中同时存在 `src/` 的调用方会观察到文件落在不同位置
- X2 改变配置文件写入的字节编码。在 Windows 上用旧版本写过含中文配置的用户，其文件是 GBK 编码；本变更的读取回退路径保证其仍可被读取，但会告警
