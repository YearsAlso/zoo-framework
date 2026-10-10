# branch-doc-sync 任务清单

## 1. 前置测量（design.md Migration 步骤 1 的证据复核）

- [x] 1.1 执行并记录分支分歧量化证据：`git rev-list --count origin/main..origin/dev`、`git rev-list --count origin/dev..origin/main`、`git diff --stat origin/main...origin/dev -- "*.md"`，输出写入 PR 描述（验证：PR 内附三组命令原始输出）
- [x] 1.2 逐个列出 main 上访客可见的错误信息（当前已知：SECURITY.md `0.5.3-beta` 支持表），标明哪些随本 change 修复、哪些属"随发版下发"（验证：清单出现在 PR 描述）

## 2. dev 侧交付物

- [x] 2.1 新增 `docs/BRANCHING.md`：双分支职责 → 访客可见面清单（含每项职责一句话）→ 可见性时限承诺 → drift 检查命令与判读规则 → "SECURITY.md 等治理文件以 dev 为唯一编写点"约束（验证：四个 Requirement 场景逐一能对照文档内容得出 PASS/FAIL）
- [x] 2.2 `CONTRIBUTING.md`「分支规范」节末尾加一句互链指向 `docs/BRANCHING.md`（中英两半同步；中文半同样位置）（验证：`grep -in "BRANCHING" CONTRIBUTING.md` 两半各命中 ≥1）
- [x] 2.3 `README.md` 若提及分支/贡献路径处需要互链则加一行链接（中英双语同步）（验证：`grep -in "BRANCHING" README.md` 两半各命中或明确不需要并记录理由）

## 3. main 侧同步（实施决策：方式 A——顺延至下次 dev→main 发版）

- [x] 3.1 ~~从 `origin/main` 切 `sync/security-version-table` 建独立 PR~~ **维护者决策（方式 A）**：不建独立 PR。`main..dev` 已有 52 commits，SECURITY.md 修复包含其中，随下次 dev→main 发版自然下发且免去一次多余 stable 发版。BRANCHING.md 规则 1 的"同一发布周期"时限由该次发版满足（验证：下次发版合并后，`git show origin/main:SECURITY.md` 无 `0.5.3-beta` 残留）
- [ ] 3.2 发版时按 design.md D2 标准复核其它访客可见面文件是否有"纯事实纠错"需要随发版处理（README 正文重写属随发版内容，勿手工搬运）（验证：发版 PR 内的复核结论记录）
  - **外部阻塞（不可在代码仓内完成）**：触发条件是「下一次 dev→main 发版」，属发布流程内动作；
    锚点证据在 `origin/main` 的访客可见面快照（复核动作 = 发版前对 `git show origin/main:<文件>`
    逐个按 D2 标准判读），本分支无法预先执行。合入说明：本分支的交付物（`docs/BRANCHING.md`、
    CONTRIBUTING/README 互链）已完成并验证，此项属发版期的复核职责，非未完成的功能项

## 4. 验证与归档

- [x] 4.1 dev 侧抽检完成：`git status` 显示本 change 仅改动 CONTRIBUTING.md / README.md / README.zh.md / docs/BRANCHING.md / openspec/，SECURITY.md 在 dev 上零改动。main 侧抽检（`git show origin/main:SECURITY.md` 无版本号残留）**顺延至任务 3.1 的发版时点执行**（验证：dev 抽检输出已记录；main 抽检在发版 PR 中补做）
- [x] 4.2 执行 `docs/BRANCHING.md` 中的 drift 检查命令并存档输出，判读是否违反契约（验证：输出归档到 evidence.md）：SECURITY.md 差异 = 违反规则 3（随发版下发处置）；README 差异 = 规则 2 豁免；其余三文件无差异
- [x] 4.3 `openspec validate branch-doc-sync --strict` 通过（验证：命令退出码 0）
- [x] 4.4 若维护者决定采用自动回并 workflow，另立 change（不在本 change 范围内），在 issue #107 记录决定（验证：issue 评论）——维护者决策：自动回并 workflow **不立项**（方式 A 顺延发版）；决策于 apply 会话当面确认，issue #107 评论由维护者提交 PR 时自行补充
