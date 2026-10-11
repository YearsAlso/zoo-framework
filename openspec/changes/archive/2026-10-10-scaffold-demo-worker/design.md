# 技术设计：scaffold-demo-worker

## 决策

### D1: demo Worker 的生成方式——复用 `worker_template` 渲染，不新造模板

`create_func` 内部用与 `worker_func` 完全相同的 `Template(worker_template)` 渲染一个
`sample_worker`，产出 `src/workers/sample_worker.py`，类名 `SampleWorker`。
不新建第二套模板的好处：模板的产品语义（"模板产出的代码 MUST 直接可用"）只有一份
真源，后续对模板的任何修复自动覆盖 demo。

备选：在 `worker_template` 里内嵌 `if DEMO:` 分支渲染——拒绝，模板里出现死分支
违背"产出物即真源"。

### D2: 预注册进入口——直接改 `main_template`，不动 `WORKER_REGISTRATION_MARKER` 机制

`main_template` 的 `WORKERS` 列表在标记之外**静态预置**
`("SampleWorker", SampleWorker),` 一行（导入行同理）。`zfc --worker` 的幂等接线逻辑
（按整行判重）对已存在的静态条目天然无感，重复执行 `--worker sample_worker` 时
`_wire_worker_into_main` 不追加重复行——零改动获得共存保证（spec Scenario"示例 Worker
与后续新增 Worker 共存"由此 Scenario 直接覆盖，无需新代码）。

备选：运行时注入（create_func 创建后二次编辑 main.py）——拒绝，两段产出路径
（模板直出 + 事后编辑）会让产物形态很难单点推理；模板直出是唯一真源。

### D3: `_execute()` 输出形态——单行、含名字与自增计数

模板 `_execute` 改为维护 `self._tick = 0` 并输出
`print(f"[{self.props['name']}] tick #{self._tick} ...")`。
计数从 1 起算，保证"连看两次输出单调递增"可测。打印走 `print` 而非日志：demo 的
目标是**绕过刷屏日志被人眼看到**，日志走的是会被 B2（#111 日志降噪）统一治理的
通道，不适合承载"用户自己的输出"这一语义。

### D4: 成功摘要打印位置——`create_func` 末尾，不经过 click

`create_func` 末尾按固定格式向 `sys.stdout` 打印三行摘要（位置 / 文件量 / 下一步
命令）。测试既有 `TestCliOptions.test_create_produces_output` 断言 exit_code 与
产物存在，不约束 stdout 内容，无冲突。摘要的"文件量"以 create_func 实际写入的
文件清单长度为准（计数源 = 产出的那个列表本身，不自建第二份清单）。

### D5: 测试意图变更标注——`WORKERS == []` 断言翻为非空

`test_entry_imports` 的 `assert module.WORKERS == []`（templates.py L81）改为
非空并断言含 `SampleWorker` 条目——这是行为意图变更（spec 直接驱动的改变），
在用例 docstring 中标注"行为意图变更：#110，默认产物从空注册变为预置 demo"。
其余既有断言一律不放宽；`TestDocsMatchImplementation.test_documented_examples_run_successfully`
会自动把 README 改后的命令序列跑一遍，README 与实现一致性测试不需要新机制。

### D6: README 期望输出贴文——贴"过滤日志后"的真实业务行走文本

README Quick Start 代码块后贴出的期望输出**只贴 demo Worker 的业务行**
（`[SampleWorker] tick #1` 板式），并注明框架的系统日志会长这样（指引 B2 降噪）。
不贴整屏混排日志——那取决于 B2 的落地时点，贴了就会漂移。

## 实测基线（复现数据）

- `WORKERS == []`：导入 `src/main.py` 后逐字检查成立；
- 可见输出 100% 来自 LogUtils；`grep -v LogUtils` 后零行业务行；
- `zfc --worker sample_worker` 现有幂等接线按行判重，预置条目不会重复追加。
