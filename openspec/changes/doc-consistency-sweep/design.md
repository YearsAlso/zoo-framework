# 技术设计：doc-consistency-sweep

## 现状梳理

基线 = dev 0.10.6-beta（1083508）+ perfect/docs 6 提交。issue #114 写作时对标的
是旧文档形态；PR #140/#146 的文档重建已消化其中 2.5 条（README 数字、#9 待办、
#10 bumpversion），但 5 条仍在，且各自换了藏身处：

1. **测试数字**：README 已"徽章化"（无数值），但 `docs/contributing/structure.md`
   L18/L168 仍硬编码 `367 cases, 23 files`（实测 1024/37 文件）
2. **SVM 宣称**：README 与 ARCHITECTURE.md L362 已诚实，但 ARCHITECTURE.md L86
   "关键特性"清单与 roadmap.md L15"自动故障检测"仍无标注
3. **ELS 背书**：roadmap.md L15/L301、internal/business-plan.md L62
4. **隐喻表两套**：CLAUDE.md L11-15（Zookeeper/Food/Feeder，代码零引用）vs
   README.md L257-267（= 代码实况）；docs/README.md L170 列举缺 Reactor/StateMachine
5. **Python 3.8 残留**：docs/contributing/development.md L11、L355

## D-Decisions

### D1: 修"宣称的内容"而非"数值"——数字一律徽章化或快照化

structure.md 的用例数属"随每次合并漂移的数字"，人工维护必错。选择：
- structure.md 面向贡献者速览，保留行但改为不含具体数（"以 Tests 徽章为准"），
  加一致性测试断言该文件不含 `\d+ cases?` / `\d+ 条用例` 字样——**故意改回数字
  即红**，有牙齿（验收要求演示）。

### D2: 隐喻表以 README 为唯一真源，测试解析三处表格做映射集合比对

README 表（8 行：Worker/Master/Waiter/Cage/Event/FIFO/Reactor/StateMachine）=
 代码实况。CLAUDE.md 表整表替换。测试解析各文件的 markdown 表格提取
(隐喻, 组件) 对，归一化后比较集合；同时断言禁用映射（Zookeeper、Food、
Feeder）不出现在任何隐喻表的组件列。解析容错：允许语言/emoji/粗体差异，
按"隐喻单元格 → 组件单元格"的列位提取并归一化组件名（剥反引号/粗体）。

### D3: SVM 与 ELS 是"措辞诚实化"，不引入新机制

- ARCHITECTURE.md L86 `SVM 健康监控` → `SVM 健康监控（指标链路尚未接通）`
- roadmap.md L15 `SVM 状态监控，自动故障检测` → 拆分为"SVM 状态监控（指标链路
  尚未接通，健康报告恒为 0）"；`已在 ELS 项目中实际应用验证` →
  `在维护者的内部生产项目中经过实测（不出自公开可复现的基准，详见 docs/benchmark.md）`
- roadmap.md L301 章节同改
- internal/business-plan.md L62 同改（虽不进站点，仓库内一致）
- 背景：README L255-256 已有诚实标准句，措辞对齐它

### D4: Python 门槛以 pyproject 为真源，测试双向核对

development.md L11 `| Python | 3.8 | 3.11 |` → `| Python | 3.13 | 3.13 |`；
L355 `Python 3.8+ 已安装` → `Python 3.13+ 已安装`。
测试：解析 `requires-python = ">=3.13"`，断言"文档中提到的最低 Python 版本"
与之相容——实现为**禁用词路线**（`3.8`/`3.11` 不得再出现在环境要求上下文）+
pyproject 真源断言。3.10–3.12 在 FAQ/install.md 是"被排除人群"的讨论，合法。

### D5: 一致性测试并入 tests/test_doc_consistency.py（文件已存在）

该文件已有 7 条（mkdocstrings 目标 / import 可执行 / 链接可解析），复核时其
注释/排除规则成熟（internal/ 已被排除出可发布文档、HTML 注释剥离器已备）。
新增一个 class：`TestPublishedClaimsMatchReality`，4 条测试：
1. `test_no_hardcoded_case_counts`：structure.md（+白名单 None）不含具体用例数
2. `test_python_floor_claims_match_pyproject`：development.md 环境表取到的最低
   版本 == pyproject requires-python 解析值；禁用 `3.8`
3. `test_metaphor_tables_converge`：三处表映射集合一致 + 禁用旧映射
4. `test_no_dead_health_claims`：全 docs + zoo_framework 源 grep
   `SVM monitoring started` == 0；roadmap/ARCH 的 SVM/ELS 宣称处出现
   "尚未接通"标注（用关键句存在性断言）

### D6: 测试须有牙齿（assertion-integrity 规则）

验收要求"故意改坏 → 红 → 改回 → 绿"。设计上每条断言都以"删掉文档修复内容/
恢复硬编码数字"为注入点注入违规后确认红。注入走 `.claude/workflows/bugfix.md`
串行纪律（VIOLATION- 标记 + md5 还原核对）。

## 风险

- **表格解析脆弱**：README 表是宽表（长行），CLAUDE.md 表列位一致；解析按
  `|` 拆列取前两列，遇 3 列 markdown 表即工作。风险可控——解析器只处理这 3 个
  已知文件，写死路径而非全 docs 扫描。
- **"ELS 也出现在 internal/"**：internal/ 不进站点，但为仓库内一致仍修；
  不给 internal/ 加测试约束（它不是对外承诺）。
- **roadmap 其他段落的相似宣称**：L301-304 区块同改，但"处理过生产环境高并发
  场景"等语录属同一背书块，一并落在该块的改写里，不扩散到无关段落。
