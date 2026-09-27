## 1. 前置：依赖确认与基线

- [x] 1.1 确认硬依赖已满足：`fix-worker-scheduling` 的任务 6.5（运行期注册的 Worker 进入调度）与 6.2（停机触发 Worker 销毁钩子）已落地；验证：`Master.register_worker` 注册的 Worker 在下一轮 `execute_service()` 中被实际执行；`Master.shutdown()` 会调用已注册 Worker 的销毁钩子。**未满足时 S2 与 S7 无法成立**，不得通过放宽断言绕过
- [x] 1.2 记录改动前的测试基线；验证：`pytest -q` 全绿，用例数记录在提交说明中（本机使用 `.venv/Scripts/python.exe -m pytest`，裸 `python` 指向仓库内 3.9 的 `venv/`）
- [x] 1.3 在临时目录实际生成一次脚手架并留存证据；验证：产物目录树、`main.py`、`*_worker.py`、`config.json`、各 `__init__.py` 的内容已记录，作为改动前后的对照基线
- [x] 1.4 逐条复现 `proposal.md · Why` 中列出的四个断点；验证：① 导入生成的 worker 抛 `ImportError`；② `Master(worker_count=5)` 抛 `TypeError`；③ 生成的配置键 `worker.pool.enabled` 与框架查询的 `worker:pool:enable` 不一致；④ `--config` 在 `zfc` 函数体内出现 0 次引用。四条均已复现并记录命令与输出
- [x] 1.5 确认本次不触碰范围外文件；验证：`__main__.py` 的产出目录判定逻辑、`params/worker_params.py`、`core/worker_registry.py`、`core/aop/worker.py` 均未被修改

## 2. S1 · 生成的 Worker 文件可被导入

- [x] 2.1 按 design D2 从 `worker_template` 移除 `from zoo_framework import worker` 与 `@worker(count=1)`；验证：在临时目录生成的 Worker 模块可被成功导入，不抛 `ImportError`
- [x] 2.2 复核生成模块中引用的每个公开名称均可从声明的模块导入；验证：逐个对生成模块的导入语句做实际导入检查，无一个失败。**注意**：该断言不能靠字符串比对，必须真实执行导入

## 3. S3 · 生成的入口可运行

- [x] 3.1 按 design D1 修正 `main_template` 中 `Master(worker_count=5)` 为当前公开的构造方式；验证：导入生成的入口模块并调用其启动函数，构造框架对象时不抛 `TypeError`
- [x] 3.2 确认生成入口的构造调用与 `Master` 当前签名相容；验证：以生成入口中的实际调用方式构造 `Master` 成功，且该断言在 `Master` 签名变更时会失败（而非靠硬编码字面量比对）

## 4. S2 与 S6 · 生成的 Worker 被调度，且存在加载路径

- [x] 4.1 按 design D2 让生成入口显式导入并注册 Worker；验证：调用生成入口的启动函数后，`Master` 的 Worker 注册表中存在该 Worker
- [x] 4.2 按 design D3 补全产出项目中承担包角色但缺少包标识的目录（实测 `src/` 下无 `__init__.py`，而其四个子目录都有）；验证：生成项目中每个承担包角色的目录均存在包标识文件
- [x] 4.3 确认生成的 Worker 模块存在从入口出发可追踪的加载路径；验证：从生成入口出发追踪模块加载，该模块在路径上被加载；不存在"已生成但从不被加载"的模块
- [x] 4.4 触发调度轮次并断言生成的 Worker 被执行；验证：注册后调用 `execute_service()`，该 Worker 的执行计数增加。**该断言依赖 1.1**，若依赖未满足应如实呈红而非绕过
- [x] 4.5 复核生成入口不依赖 Worker 包初始化文件来启用 Worker；验证：单独删除 `workers/__init__.py` 中的导入行不影响 Worker 被加载（显式导入路径应自足）

## 5. S4 · 生成的配置被框架实际读取

- [x] 5.1 复核 `fix-worker-scheduling` 任务 5.1 已解决 `worker:pool:enabled` 与 `worker:pool:enable` 的键名不一致；验证：以脚手架生成的 `config.json` 初始化 `ParamsFactory` 后，`WorkerParams.WORKER_POOL_ENABLE` 取到的值等于配置文件中声明的值而非默认值。**本变更不重复修复该键名问题**，只补端到端断言
- [x] 5.2 补齐配置生效的端到端用例；验证：用例使用脚手架**实际生成**的配置文件（而非手工构造的），断言每一项声明都能被框架的配置读取路径取到非默认值
- [x] 5.3 复核生成配置中不存在框架从不查询的键；验证：比对生成配置的键结构与框架实际查询的键路径，无孤键。若发现孤键，登记为后续项而非在本变更内静默删除

## 6. S7 · 模板钩子名与框架一致

- [x] 6.1 确认 `fix-worker-scheduling` 任务 6.2 落地后框架在停机时实际调用的钩子名；验证：该钩子名有明确的实现依据（可指向具体代码位置），而非推测
- [x] 6.2 按 design D5 使 `worker_template` 中的钩子名与该名称一致，并移除框架从不调用的钩子；验证：取出模板中示范的全部钩子名，与框架实际调用的钩子名集合比对，模板中的每个名字都在集合内
- [x] 6.3 补齐钩子名一致性的回归用例；验证：该用例在模板新增一个框架不调用的钩子时会失败（而非仅断言当前名单）

## 7. S5 · CLI 选项具备真实语义

- [x] 7.1 复核 `zfc --config` 已被移除（**实现由 `fix-cross-platform-defects` 交付**，该变更在修产出目录定位时同处 `zfc` 命令定义）；验证：`zfc --config foo` 明确报错指明该选项不受支持，而非静默接受并正常退出。本变更只补断言，不重复实现
- [x] 7.2 逐一核对其余选项的实际效果；验证：`--create` 与 `--worker` 各自产生可观察的输出差异，且该差异被用例断言
- [x] 7.3 补齐 CLI 选项的回归用例；验证：用例逐一使用暴露的每个选项并断言产生了效果——当新增一个无效果的选项时用例会失败

## 8. 端到端验收（design D1 的契约）

- [x] 8.1 建立一条端到端用例：在临时目录生成 → 导入生成入口 → 调用启动函数 → 触发调度 → 断言 Worker 被执行；验证：用例在改动后的代码上通过
- [x] 8.2 确认该用例在改动前的代码上失败；验证：以 `git stash` 撤回改动后重跑该用例，失败原因与 1.4 复现的断点一致（而非因用例自身错误而失败）
- [x] 8.3 确认端到端用例不依赖真实项目结构与无限循环；验证：用例在临时目录内运行，不进入 `master.run()` 的无限循环，且不依赖 `fix-cross-platform-defects` 的 X1 修复即可运行（如需可自行指定产出目录）

## 9. 收尾验证

- [x] 9.1 全量回归；验证：`pytest -q` 全绿，用例数不少于基线（1.2）
- [x] 9.2 生成一份新的脚手架产物并与 1.3 的基线逐项对照；验证：四项断点全部消失，且产出的模块数量、包结构自洽
- [x] 9.3 确认未夹带范围外改动；验证：`git diff --stat` 限于 `zoo_framework/templates/__init__.py`、`zoo_framework/__main__.py`、`tests/`，外加 `zoo_framework/utils/file_utils.py` 的换行处理修复——生成入口需要「读出再写回」，而平台换行翻译会让 CRLF 在每次往返中多出一个 `\r`，该修复是其前置条件
- [x] 9.4 确认未引入新依赖；验证：`pyproject.toml` 的 `dependencies` 未变化
- [x] 9.5 在发布说明中给出新旧脚手架产物的对照与 `--config` 移除的说明。**载体说明**：仓库既无 CHANGELOG，`release.yml` 的 GitHub Release 正文又由 `git log` 的提交信息生成，因此落点是 **commit message 正文**。已把完整文本写入 `release-notes.md`，提交时需原样并入提交信息
- [x] 9.6 复核与 `fix-cross-platform-defects` 的边界未被跨越；验证：本变更未修改产出目录的判定逻辑，该变更未修改模板内容。两个变更的 `cli-scaffolding` 与 `project-scaffolding` 能力可分别验收
- [x] 9.7 复跑 OpenSpec 校验；验证：`openspec validate --all` 全绿
