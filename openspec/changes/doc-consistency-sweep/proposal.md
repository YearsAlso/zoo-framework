# 提案：doc-consistency-sweep

## Why（为什么）

对框架项目，**文档前后一致本身就是产品可靠性**。逐条独立复核（2026-10-10，
基线：本分支 = dev 0.10.6-beta + perfect/docs 6 提交，实测全量 pytest = **1024 passed**）
.issue #114 列出的 10 处矛盾中，5 处在 dev 近两日的文档重建后形态已变，需要按**当前
证据**重新定性；5 处仍然成立。这些矛盾靠人眼核对必然复发，必须把可机械判定的部分
变成 CI 能拦下的测试。

## What Changes（做什么）

本 issue 只修第 1 / 2 / 3 / 4 / 5 条；第 6–10 条记录并移交对应 issue（避免重复劳动）。

### 逐条复核核对表（10 条 → 处置）

| # | issue 里的表述 | 当前实测证据（行号） | 定性 | 处置 |
|---|---|---|---|---|
| 1 | 测试数量三个版本（367/662 vs 实测） | README.md L168-170 已改为"持续通过的回归套件 + Tests 徽章"（无具体数字）；**仍成立处**：`docs/contributing/structure.md:18` `367 cases, 23 files`、`:168` `367 条用例，23 个文件`（实测 **1024**，远超）；PR #146 后 README 已无数值 | **部分成立**（数字硬编码在 structure.md） | **修**：structure.md 数值改为与实况一致口径 + 一致性测试拦数字漂移 |
| 2 | 健康监控宣称已接通 vs 承认未接通 | README.md L255-256 `⚠️ Metric pipeline not yet wired`（诚实）；docs/ARCHITECTURE.md L362 标题已带「指标链路尚未接通」副标；**仍成立**：docs/ARCHITECTURE.md L86 `SVM 健康监控`（关键特性列表，无未接通标注）；roadmap.md L15 `SVM 状态监控，自动故障检测`；运行时日志已修（B2：`metrics input not wired`，`SVM monitoring started` 字样已不存在） | **部分成立**（roadmap + ARCHITECTURE L86 两处过度宣称仍在） | **修**：roadmap L15 与 ARCHITECTURE L86 补「指标链路尚未接通」标注 |
| 3 | 「已在 ELS 项目实际应用验证」不可核实 | **成立**：docs/contributing/roadmap.md:15、:301；docs/internal/business-plan.md:62（internal/ 被 mkdocs exclude_docs 排除、不进站点，但仓库内仍误导） | **成立** | **修**：roadmap 两处改为可核实的表述（私有项目名删除，改为"内部项目实测"并连线到 issue 账本）；internal/business-plan.md 同步 |
| 4 | 隐喻映射表两套 | **成立**：CLAUDE.md L11-15（Animal/Cage/Zookeeper=Master/Food/Feeder queue）对照 README.md L257-267（Worker/Master/Waiter/Cage/Event/FIFO/Reactor）——**code 实况以 README 版为准**（Zookeeper/Food/Feeder 在代码里零匹配）。docs/README.md L170 列举 `Worker / Master / Waiter / Cage / Event / FIFO` 与 README 表一致但缺 Reactor/StateMachine | **成立** | **修**：CLAUDE.md 表改为 README 版（代码实况）；docs/README.md L170 列举补全 |
| 5 | Python 版本陈述陈旧（3.8+ 残留） | **成立**：docs/contributing/development.md:11 `Python | 3.8 | 3.11`、:355 `Python 3.8+ 已安装`（pyproject 是 `>=3.13`） | **成立** | **修**：两处改为 3.13 / 3.13+，一致性测试从 pyproject 读 `requires-python` 比对 |
| 6 | CHANGELOG 断档（0.8.0 → 37 个 PyPI 版本） | **成立**：CHANGELOG.md 仍只有 Unreleased + 0.8.0 两条 | **成立** | **移交 → #117**（issue 本来的归属） |
| 7 | "无 broker" vs example/config.json `"_exports": ["redis"]`；redis.json 存在、产品代码 redis 零引用 | **成立**（实测 `zoo_framework` 内 redis 零匹配；example/main.py 也无） | **成立** | **移交 → #116** |
| 8 | example/agent 空 submodule，README 未提 `--recursive` | **成立**（.gitmodules 指向 zoo-code-agent） | **成立** | **移交 → #116** |
| 9 | 发布物泄漏作者待办 | **已被后续文档重建基本消化**：README.md L33 只剩一个 HTML 注释占位 `<!-- TODO(demo): docs/assets/demo.gif -->`（不渲染，不算泄漏）；原 L141-150/L506-515 的待办清单在 PR #146 后不存在 | **已不成立** | **无需修**；#109 若仍追待办治理可另核 |
| 10 | bumpversion current_version 0.8.0 vs version 0.10.0 | **已不成立**（rebase 后 pyproject 为 0.10.6-beta；`[tool.bumpversion] current_version` 已不存在，bump-my-version 配置取代） | **已不成立** | **移交 → #115 复核时顺带销案** |

### 修复动作（仅 1-5）

1. **test-count / version 口径**：`docs/contributing/structure.md` 两行改为不含具体
   数值的说法（指向 Tests 徽章）， 因为数值随每个合并漂移、人工维护必错——机制化：
   一致性测试断言"structure.md 不得出现具体用例数"或与其维护策略联动的快照
2. **SVM 宣传口径**：roadmap.md L15、ARCHITECTURE.md L86 补「指标链路尚未接通」
3. **ELS 不可核实背书**：roadmap.md L15/L301、business-plan.md L62 改为不依赖私有
   项目的可核实表述
4. **隐喻表**：CLAUDE.md 表改为与 README.md Core concepts 完全一致（后者 = 代码实况）；
   docs/README.md L170 列举补 Reactor / StateMachine
5. **Python 版本**：development.md 两处 3.8 → 3.13
6. **新增 `tests/test_doc_consistency.py` 组**（文件已存在，扩展）：
   - meta-version：pyproject `version` / `requires-python` vs 文档出现值
   - 测试数量：文档里硬编码的用例数必须等于实测 collect 数或直接禁止数字（选后者，快照防漂移）
   - 隐喻映射表：三份文件（README.md / README.zh.md / CLAUDE.md）的表内容一致
   - 禁用词快照：`SVM monitoring started` 等已废弃宣称词不得在文档/日志出现

## Capabilities（能力）

- **New**: `docs-consistency` — 文档与实况的机械一致性契约（本 change 新建 spec）
- **Modified**: 无（首次建立）

## 影响（Impact）

- 文档：`docs/contributing/structure.md`、`docs/contributing/roadmap.md`、
  `docs/contributing/development.md`、`docs/ARCHITECTURE.md`、`docs/README.md`、
  `docs/internal/business-plan.md`、`CLAUDE.md`
- 测试：`tests/test_doc_consistency.py` 扩展
- 不碰：CHANGELOG（#117）、example/（#116）、pyproject/发布流程（#115）、README 演示图（#109）
