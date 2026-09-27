## 1. 前置：基线与影响面

- [x] 1.1 记录改动前的测试基线；验证：`pytest -q` 全绿，用例数记录在提交说明中（本机使用 `.venv/Scripts/python.exe -m pytest`，裸 `python` 指向仓库内 3.9 的 `venv/`）
- [x] 1.2 复现三项缺陷并留下可复现证据；验证：① 含中文的 UTF-8 配置文件在 `cp936` 环境下被静默读错；② 同一秒内 3 次备份只产出 1 个文件；③ 日志在 `cp936` 输出目标上整行丢失。三条均已复现并记录命令与输出
- [x] 1.3 按 design D1 确认影响面清单；验证：`grep` 找出的文本模式 `open()` 未声明编码的位置与 `proposal.md · Impact` 一致（当前为 16 处），二进制模式的位置已排除
- [x] 1.4 确认本次不触碰范围外文件；验证：`utils/thread_safe_dict.py`、`.github/workflows/release.yml`、`templates/__init__.py` 均未被修改

## 2. X2 · 文本 I/O 编码（影响最大，优先修复）

- [x] 2.1 按 design D1 修复配置文件的读写编码（`core/params_factory.py:13,16,41`）；验证：在 `cp936` 环境下读取含中文的 UTF-8 配置文件，得到的值与该文件的真实内容一致（对照改前实测的 `'璋冭瘯'` 损坏结果）
- [x] 2.2 按 design D1 修复校验和文件与工具类的文本 I/O（`core/persistence_scheduler.py:131,148`、`utils/file_utils.py:61`）；验证：`grep -rn "open(" zoo_framework/ | grep -v encoding` 不再命中文本模式的位置
- [x] 2.3 按 design D1 修复脚手架文件写入的编码（`zoo_framework/__main__.py` 的 9 处）；验证：在 `cp936` 环境下执行脚手架命令，产出文件按 UTF-8 可正确读回
- [x] 2.4 按 design D1 实现读取回退：先 UTF-8，`UnicodeDecodeError` 时回退到平台默认编码并输出含文件路径的 WARNING；验证：分别用 UTF-8 与非 UTF-8 编码写入同一内容，两次读取结果一致；回退时告警存在且告警文本包含文件路径
- [x] 2.5 补齐编码回归用例，且用例 MUST 在任意单平台上可复现（通过显式构造不同编码的文件，而非依赖运行平台的 locale）；验证：在不改变运行平台的前提下，用例能覆盖 UTF-8 路径与回退路径两条分支
- [x] 2.6 复核回退分支未被静默化；验证：用例断言回退时**确实**产生了 WARNING（`caplog` 或等价机制），而非仅断言读取成功

## 3. X3 · 日志编码

- [x] 3.1 按 design D2 为控制台日志 handler 显式声明编码与错误处理策略（`conf/log_config.py:42`）；验证：向编码能力受限的输出目标写含 emoji 的日志时，不抛 `UnicodeEncodeError`，且整条日志被写出
- [x] 3.2 按 design D2 处理结构化日志的流输出（`utils/structured_log.py:84`）；验证：同一条件下不抛异常，内容完整
- [x] 3.3 确认日志文件 handler 也以 UTF-8 写出；验证：读取日志文件，其中的 emoji 保持原样未被降级
- [x] 3.4 补齐日志编码回归用例；验证：用例在编码能力受限的输出目标上断言"整行存在且非空"，并断言降级形式保留了原始码位信息（可还原）

## 4. X4 · 备份命名唯一性

- [x] 4.1 按 design D3 提升 `core/persistence_scheduler.py:180` 的时间戳精度；验证：同一秒内连续 3 次备份产出 3 个不同文件，且各自内容对应其备份时的源文件状态
- [x] 4.2 按 design D3 提升 `workers/state_machine_work.py:150` 的时间戳精度；验证：同上
- [x] 4.3 确认命名仍满足"字典序等于时间序"；验证：构造一组备份文件后，按名称排序的结果与按创建时间排序的结果一致（该性质被既有的 `glob` + `sort(reverse=True)` 取最新逻辑依赖）
- [x] 4.4 确认新旧命名混排时"取最新"仍正确；验证：在备份目录中同时放入旧命名与新命名的文件，断言取出的确实是最新的那个
- [x] 4.5 确认 `glob` 模式未变、既有备份仍可被发现；验证：`state_machine_*.pkl` 与 `*.bak` 模式未修改，旧文件仍能被列出与恢复

## 5. X1 · CLI 产出目录定位

- [x] 5.1 按 design D4 改写 `zoo_framework/__main__.py:65` 的目录判定：依据 `./src` 是否存在且为目录决定产出到 `./src/workers` 还是 `./workers`，不再读取 `sys.argv[0]`；验证：`grep -n "sys.argv" zoo_framework/__main__.py` 无结果
- [x] 5.2 确认判定覆盖两种真实用法；验证：在含 `src/` 的项目根执行命令，文件落在 `src/workers/`；在不含 `src/` 的位置执行，文件落在 `workers/`
- [x] 5.3 确认判定不依赖进程启动方式；验证：分别以可执行入口与模块方式（`python -m zoo_framework`）在相同工作目录结构下执行，两次产出位置一致
- [x] 5.4 确认产出目录不存在时被正确创建；验证：在空目录执行命令，目录被创建且文件写入成功
- [x] 5.5 补齐 CLI 定位回归用例；验证：用例使用临时工作目录切换 `cwd`，不依赖真实项目结构，且不依赖运行平台

## 6. 收尾验证

- [x] 6.1 端到端复跑 1.2 的三条复现；验证：三条缺陷均不再复现——配置文件在 `cp936` 环境下读出正确值；同一秒 3 次备份产出 3 个文件；日志整行不丢失
- [x] 6.2 全量回归；验证：`pytest -q` 全绿，用例数不少于基线（1.1）
- [x] 6.3 确认跨平台门禁能实际拦截；验证：`tests.yml` 的 ubuntu / windows / macos 三个 job 均通过，且 2.5 与 5.5 的用例在任意单平台上均可运行（不因平台被 skip 而失去覆盖）
- [x] 6.4 确认未夹带范围外改动；验证：`git diff --stat` 限于 `zoo_framework/__main__.py`、`core/params_factory.py`、`core/persistence_scheduler.py`、`workers/state_machine_work.py`、`conf/log_config.py`、`utils/structured_log.py`、`utils/file_utils.py` 与 `tests/`
- [x] 6.5 确认未引入新依赖；验证：`pyproject.toml` 的 `dependencies` 未变化
- [x] 6.6 复跑 OpenSpec 校验；验证：`openspec validate --all` 全绿
- [x] 6.7 在发布说明中单列 X1 的行为变更（产出目录改变）与 X3 的预期表现（emoji 在受限控制台降级为转义序列而非丢失整行）。**载体说明**：仓库既无 CHANGELOG，`release.yml` 的 GitHub Release 正文又由 `git log` 的提交信息生成，因此发布说明的落点是 **commit message 正文**。已把完整文本写入 `release-notes.md`，提交时需原样并入提交信息
