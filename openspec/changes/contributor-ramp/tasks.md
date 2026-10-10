# contributor-ramp 任务清单

## 1. 拆分 `CONTRIBUTING.md`（design D1 / D2）

- [x] 1.1 `git mv CONTRIBUTING.md docs/CONTRIBUTING_MAINTAINER.md`，完整规范**逐段保留**
      （验证：`git status` 显示为 rename（`R CONTRIBUTING.md -> docs/CONTRIBUTING_MAINTAINER.md`）；
      原 **12** 个英文 `###` 标题与 **12** 个中文 `###` 标题全部可定位——共 24 个；
      搬移 + 新增第 6 节两小节后每半 14 个，全文 604 行）
- [x] 1.2 维护者版的语言锚点改为显式 ASCII id：`## 🇬🇧 English {#en}` /
      `## 🇨🇳 中文 {#zh}`，页内链接改为 `[English](#en) | [中文](#zh)`
      （缩写跟随 `docs/benchmark.md` / `docs/contributing/structure.md` 的既存惯例）
      （验证：`pytest tests/test_doc_consistency.py::test_no_cjk_anchor_links` 通过；
      该文件搬入 `docs/` 后**不改必红**）
- [x] 1.3 维护者版的跨 `docs_dir` 链接改写为 dev 分支绝对 URL：`SECURITY.md`、
      `CODE_OF_CONDUCT.md`、`.github/PULL_REQUEST_TEMPLATE.md` →
      `https://github.com/YearsAlso/zoo-framework/blob/dev/<path>`；`docs/BRANCHING.md` →
      同目录相对链接 `BRANCHING.md`
      （验证：`pytest tests/test_doc_consistency.py::test_relative_links_resolve` 通过；
      非 strict `mkdocs build` 的新增链接告警为 0）
- [x] 1.4 维护者版首部加一段定位说明：本文是**完整维护者规范**，面向"改这个仓库的人"；
      精简入口在仓库根 `CONTRIBUTING.md`
      （验证：文件首屏含该定位句与指向根入口的链接）
- [x] 1.5 重写根 `CONTRIBUTING.md` 为精简入口（**总计 ≤100 行、每半 ≤60 行**），两半各含
      五类内容：建环境 → 跑测试 → 提 PR → 免流程改动 → 怎么提问；每半给出可执行的具体做法
      （命令 / 链接 / 模板）并链到 `docs/CONTRIBUTING_MAINTAINER.md`
      （验证：`wc -l` ≤100；两半各自的五类内容均可定位；每半各含一条维护者版链接）

## 2. 免流程通道与门槛表述（design D3 / D4）

- [x] 2.1 在精简入口**每一半的前 20 行内**（语言标题下、第一个 `###` 之前）放一段引用块，
      明写：拼写 / 文档 / 示例 / 注释类改动**不需要** OpenSpec 提案，直接开 PR；
      完整规范见维护者版
      （验证：取两半各自前 20 行，均能匹配免流程声明；两半各含维护者版链接）
- [x] 2.2 门槛表述改为分类式：涉及**外部可观察行为、兼容性或数据格式**的改动需先写提案，
      其余由 CI 与评审把关；**删除/改写**"一律必须走 OpenSpec"式绝对表述
      （验证：精简入口与维护者版中均无法匹配"一律必须走 OpenSpec"式的绝对表述；
      两处均出现"外部可观察行为"这一分类表述）
- [x] 2.3 `.github/PULL_REQUEST_TEMPLATE.md` 的 `openspec/ —— delta spec 已提交` 勾选项旁
      补"不适用（免流程改动：拼写 / 文档 / 示例 / 注释）"允许项
      （验证：该条目含"不适用"字样；文件其余勾选项与中文双语结构不变）

## 3. 收敛重叠文档（design D5）

- [x] 3.1 `docs/contributing/contributing.md` 收敛为指针页：贡献方式概述 + 指向
      `CONTRIBUTING_MAINTAINER.md` 的链接 + 指向 `development.md` / `BRANCHING.md` 的分流；
      删除其中"从 main 分支创建功能分支"等与双分支模型矛盾或重复的内容
      （验证：该文件不再含"从 main 分支创建"；含指向维护者版的链接；行数大幅下降）
- [x] 3.2 `docs/contributing/README.md` 分区表更新三者的分工（入口 / 完整规范 / 概述与分流）
      （验证：表中"贡献指南"一行的说明不再声称覆盖"分支规范、提交规范、质量门禁、OpenSpec 流程"）
- [x] 3.3 `mkdocs.yml` 的 nav 新增 `维护者规范: CONTRIBUTING_MAINTAINER.md` 与
      `Good First Issue: GOOD_FIRST_ISSUES.md`（挂在"贡献者"分区内）；`mkdocs.yml:21` 注释里
      "见 CONTRIBUTING.md 的分支规范"改为指向维护者版
      （验证：nav 含两个新条目；注释指向的路径真实存在）
- [x] 3.4 `docs/BRANCHING.md` **不改动**（其死链是 GFI-2 的交付物）
      （验证：`git diff --stat` 中不出现 `docs/BRANCHING.md`）

## 4. good-first-issue 落地（design D7）

- [x] 4.1 新建 GFI-2 的 issue（修文档站唯一死链 `docs/BRANCHING.md:4 → ../CONTRIBUTING.md`），
      正文含文件路径 / 量级 / 验收标准（非 strict `mkdocs build` 链接告警 1 → 0）/
      使用者可见结果；给 **#131 与本 issue** 打 `good first issue` 标签
      （验证：`gh issue list --label "good first issue"` 恰好 2 条；标签已生效）
- [x] 4.2 新建 GFI-3 / GFI-4 / GFI-5 三个 issue，正文各含四要素并**显式标注阻塞来源**
      （`blocked by #110` / `#116` / `#122`），标注方式与仓库既有的 `blocked-by` 用法一致
      （验证：三条 issue 的正文均含"文件路径 / 量级 / 验收标准 / 使用者可见结果"四项与
      `blocked by #NNN`；这三条**不打** `good first issue` 标签）
- [x] 4.3 新增 `docs/GOOD_FIRST_ISSUES.md`：5 条任务表（编号 + 标题 + 文件路径 + 量级 +
      验收标准 + 使用者可见结果），并明确区分"可立即开始（2 条）"与"暂不可开始（3 条，含阻塞源）"；
      另记录两条**实测否掉**的候选方向及理由
      （验证：文件含 5 条任务且各带 issue 编号；可立即开始/暂不可开始两组分开；
      被剔除候选给出实测理由）

## 5. 贡献者收益可见（design D9）

- [x] 5.1 新增仓库根 `CONTRIBUTORS.md`：收录方式说明（按合入 PR 收录）+ 欢迎新贡献者 +
      当前名单（仅维护者），**不声称任何未经核实的第三方**
      （验证：文件含收录方式与欢迎语；`docs/GOOD_FIRST_ISSUES.md` 中至少一条可据此承诺"名字会出现在这里"）
- [x] 5.2 `README.md` / `README.zh.md` 的社区与反馈段把"尽力而为地回复"改为**可预期的承诺**，
      并以 `MAINTAINERS.md` 为唯一权威（不引入第二组天数）；同段链到 `CONTRIBUTORS.md`
      （验证：两份 README 该段均含 `MAINTAINERS.md` 链接与"7 天/7 days"首次回应表述；
      不含"尽力而为"式的低自信表述；两半段落结构平行）

## 6. 流程资产说明与门禁建议（design D6 / D8）

- [x] 6.1 维护者版新增一节说明 `.claude/` 与 `openspec/changes/archive/` 属于**流程资产**而非产品代码，
      并写明**不能移动的两条机制理由**：`.claude/` 的五个目录靠约定发现（无 `settings.json` 可重定向），
      移动即静默失效；`openspec` CLI 的 `archiveDir` 由 `path.join(rootPath, 'openspec', 'changes', 'archive')`
      **硬拼**，非配置项，移动会让 `archive` / `validate` 丢失既有归档
      （验证：该节含两条路径与两条理由；`.claude/` 与 `openspec/changes/archive/` 仍在原位置）
- [x] 6.2 维护者版新增「建议放宽的门禁（尚未生效）」小节，逐条标注为**建议、尚未生效**；
      `docs/contributing/maintainer-backlog.md` 交叉引用一行
      （验证：该小节含"建议"与"尚未生效"字样；台账页含指向该小节的链接；`.github/workflows/**` 无改动）

## 7. 机械校验（design D9）

- [x] 7.1 新增 `tests/test_contributor_ramp.py`，断言至少覆盖：
      ① 根 `CONTRIBUTING.md` 总行数 ≤100 且每半 ≤60；
      ② 每半含五类内容（建环境 / 跑测试 / 提 PR / 免流程 / 提问）与一条维护者版链接；
      ③ 每半**前 20 行内**含免流程声明（"无需提案/不需要流程"语义）；
      ④ 无"一律必须走 OpenSpec"式绝对表述，且含"外部可观察行为"分类表述；
      ⑤ 维护者版含原 **12** 个英文与 **12** 个中文 `###` 章节标题（防搬丢）；
      ⑥ 维护者版**无 CJK 锚点链接**，且含 `{#en}` / `{#zh}`；
      ⑦ 维护者版无跨出 `docs_dir` 的相对 `.md` 链接（根级文件必须用绝对 URL）；
      ⑧ `docs/contributing/contributing.md` 已不含"从 main 分支创建"且含维护者版链接；
      ⑨ `docs/GOOD_FIRST_ISSUES.md` 含 5 条任务、各带 `#NNN`、并区分可立即开始/暂不可开始；
      ⑩ `CONTRIBUTORS.md` 存在且含收录方式与欢迎语；
      ⑪ 两份 README 的贡献段都链 `MAINTAINERS.md`，且不出现与 `MAINTAINERS.md` 冲突的天数、
         不出现"尽力而为"式表述；
      ⑫ `.github/PULL_REQUEST_TEMPLATE.md` 的 openspec 条目含"不适用"；
      ⑬ `mkdocs.yml` nav 含两个新页面条目；
      ⑭ 流程资产仍在原位置（`.claude/` 五个目录存在、`openspec/changes/archive/` 存在）
      （验证：`pytest tests/test_contributor_ramp.py` 全绿——实测 **28 passed**；
      另加两条"防空跑"自检，见 7.3）
- [x] 7.2 注入违规验证断言有牙齿：串行执行、逐次按 md5 还原，至少
      ① 精简入口加一行让总行数越过 100；② 删掉某半的免流程引用块；
      ③ 维护者版删掉一个原章节标题；④ 维护者版把 `{#zh}` 改回 `#中文`；
      ⑤ `docs/contributing/contributing.md` 加回"从 main 分支创建功能分支"；
      ⑥ 从两份 README 之一删掉 `MAINTAINERS.md` 链接
      （验证：**六处注入对应的断言各自变红，还原后 md5 与打桩前逐字节一致**。
      脚本：`/f/Python/zoo/.orca/tmp-bak/contributor-ramp-apply/inject_violations.py`
      （带 `VIOLATION-` 标记、串行、逐次 `cp` 还原后比对 md5）。
      一处口径修正：入口实测 **97 行**（距上限 3 行），故 ① 注入 3 行仍合法、需注入 **5 行**
      才真正越界——任务原文"加一行"是按满行数写的，实测后按实际余量执行）
- [x] 7.3 防"空跑"自检：若某条断言的正则/切片失效导致恒真，测试必须能暴露
      （验证：新增 `test_negative_patterns_are_not_dead` / `test_free_pass_patterns_are_not_dead` /
      `test_table_and_section_helpers_are_not_dead` 三条自检——否定式规则必须命中**合成违规样本**
      且不误伤合法样本，切片助手必须取到内容、找不到标题时必须报错。
      该自检在开发期**真的红过一次**：`_ABSOLUTE_FLOW_PATTERNS` 的 `所有改动都` 匹配不到
      "所有**的**改动都必须…"，被它当场拦下并补成 `(?:所有|全部|一切)(?:的)?改动…`；
      `_section` 的切片断言误查了标题行、而非正文，同样被它拦下）

## 8. 验证与收尾

- [x] 8.1 文档站构建不回归：非 strict `mkdocs build` 退出码 0，链接告警数 = 基线 **1**
      （仅 `docs/BRANCHING.md → ../CONTRIBUTING.md`，本变更不碰），**新增 0 条**；
      新页面已随站点生成；`site/llms.txt` 与 `site/.well-known/security.txt` 仍在
      （验证：实测退出码 0、构建 3.96 s；**链接告警恰好 1 条**（BRANCHING，既存）+
      griffe 告警 40 条（既存，issue #141）——**新增链接告警 0 条**；
      `site/CONTRIBUTING_MAINTAINER`、`site/GOOD_FIRST_ISSUES`、`site/contributing` 均已生成；
      `site/llms.txt` 6083 B、`site/.well-known/security.txt` 891 B 仍在；
      构建日志留档 `/f/Python/zoo/.orca/tmp-bak/contributor-ramp-apply/mkdocs-build.log`。
      **过程中发现并修掉一处真实回归**：`docs/GOOD_FIRST_ISSUES.md` 写的
      `](../CONTRIBUTING.md)` 是 docs 根级跨出 `docs_dir` 的相对链接，会给站点**再加一条**
      死链（首次构建实测告警 2 条）。已按 D2 规则改为 dev 分支绝对 URL，并新增断言
      `test_changed_docs_pages_never_link_outside_the_site` 覆盖本变更碰过的 5 个站点页面
      ——注入 ⑦ 把该链接改回去即变红）
- [x] 8.2 全仓链接自查：`grep -rn` 核对所有指向 `CONTRIBUTING.md` 的活引用仍有效，
      且没有任何指向被移动内容的新死链
      （验证：`git grep -n "CONTRIBUTING"` 逐条实测——`GOVERNANCE.md:61/114`、
      `README.md:417/426-427`、`README.zh.md:386/394-395`、`mkdocs.yml:21/112` 全部有效；
      `docs/BRANCHING.md:24/48` 是文件名提及而非链接；`docs/` 内**唯一**跨出 `docs_dir`
      的相对链接只剩 `docs/BRANCHING.md:4`（GFI-2 的交付物，按 D 的非目标不碰）；
      `pytest tests/test_doc_consistency.py` **169 passed**）
- [x] 8.3 门禁：`ruff check zoo_framework` / `ruff format --check zoo_framework` /
      `mypy zoo_framework` / 全量 `pytest` 不回归（基线 1091 passed，+本变更新增条数）
      （验证：`ruff check zoo_framework tests` All checks passed；
      `ruff format --check zoo_framework` 107 files already formatted；
      `mypy zoo_framework` Success: no issues found in 107 source files；
      全量 `pytest` **1119 passed**，`--ignore=tests/test_contributor_ramp.py` 为 **1090 passed**，
      新文件单独跑 **29 passed**（1090 + 29 = 1119 自洽）。
      **口径修正**：任务原文写的"基线 1091"与本 worktree 实测差 1，实测值以 **1090 / 1119**
      为准。另：`ruff format --check tests` 会报 **6 个既存测试文件**需重排（`test_event.py` 等），
      属仓库既存状态、不在本变更范围，未改动）
- [x] 8.4 提交前对改动的 `.md` 先跑一次 `pre-commit run ruff-format --files <改动的 .md>`，
      把 markdown 内 ```python 围栏的重排结果一并 staged
      （验证：`pre-commit run ruff-format --files <本变动 13 个 .md>` → **Passed**，
      无需改写围栏；对本变动全部 17 个文件跑 pre-commit **全套钩子**：18 项 Passed 或
      合法 Skipped（`mypy` / `bandit` 因 `files: ^zoo_framework/` 跳过），无
      "files were modified by this hook"。
      **范围说明**：`pre-commit run --all-files` 在本仓库会报 **24 个既存文件**需重排
      （`bench/`、`docs/guides/`、`tests/*.py` 等，`ruff --fix` 还会改 `bench/measure_boundary.py`）
      ——这与本变更无关（`bench/` 本就不在 CI 门禁内，理由见 `.pre-commit-config.yaml` 的注释）。
      实测后已逐文件 `git checkout --` 还原，并用 md5 核对：`tests/*.py` 49 份全部 OK、
      本变动 17 份文件与备份逐字节一致，提交集内**零夹带**）
- [x] 8.5 `openspec validate contributor-ramp --strict` 0 警告；tasks 全勾；
      提交（`Closes #123`）+ 备份与 md5 核对
      （验证：`openspec validate contributor-ramp --strict` → `Change 'contributor-ramp' is valid`
      （无警告）；本文件全部任务置 `- [x]`；备份清单
      `/f/Python/zoo/.orca/tmp-bak/contributor-ramp-apply/md5-before.txt` 17 份文件
      `md5sum -c` 全 OK）
- [x] 8.6 如实标注生效范围：README / 文档站的改动**合并到默认分支后才对外可见**——
      本变更只保证文件、构建与 issue 就位，SHALL NOT 声称"已生效"
      （验证：提交说明与最终汇报按此口径表述，与 `#121`、`#122` 一致）
