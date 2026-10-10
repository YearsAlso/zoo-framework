# branch-doc-sync 设计

## Context

- 分支分歧（实测）：`origin/main..origin/dev` = 29 commits；`origin/dev..origin/main` = 3 commits（全部是 0.10.0 发版提交：bump + 两个 merge）。文档类 diff 约 1574 行插入，涉及 25 个文件。
- `main` 是 GitHub 默认分支，也是 mkdocs 文档站、外部搜索与 README badge 链接的默认入口。
- 已实测的具体错误（main 上可见）：`SECURITY.md` 支持版本表写 `0.5.3-beta` / "latest 0.5.x"，dev 上（#97 修复）已改为"最新 PyPI minor 线，不随版本漂移"的写法。
- dev 上的其它主分支差异（README 重写、docs/API_REFERENCE、ARCHITECTURE、新增 openspec changes）属于**功能/内容类变更**，各有独立 change 或既定发布路径，本 change 不搬运。
- 仓库已有机制先例：`release.yml` 路径 4 会在 main 发版后自动开 "back-merge main 版本线到 dev" 的 PR——**方向是 main→dev**；本问题需要的是 dev→main 的文档回并，现无任何自动化。
- `mkdocs.yml:23` 的 `edit_uri: edit/dev/docs/` 指向 dev；README 的 CI badge 硬编码 `workflows/` URL（默认跟随默认分支）。
- 发布由 push 到 `dev`/`main` 触发（`release.yml` `branches: [dev, main]`）；PR 直接进 main 的通道存在（本仓库历史有先例）。

## Goals / Non-Goals

**Goals:**
- main 上的访客可见文档不再出现"dev 已修而 main 未修"的已知错误。
- 漂移问题从"靠人记得"变成"有明确承诺 + 可执行检查"。
- 与现有双分支发布模型（dev 集成、main 发版）架构一致，不引入第三分支。

**Non-Goals:**
- 不把 dev 的功能类差异（README 重写正文、openspec changes、workflow 变更）搬进 main——它们随发版自然下发。
- 不更改发版触发、版本号机制或任何 workflow 门禁。
- 不建立'文档双写'流程（同一文档在两分支各维护一份）——那是漂移之源。

## Decisions

### D1 策略选择：c 案为主（机制化回并 + 立即修复），不反转默认分支

三案评估：

| 案 | 做法 | 收益 | 风险 | 结论 |
|---|---|---|---|---|
| a. 手工回并 | 本 PR 把 dev 的 SECURITY.md cherry-pick 回 main | 最小改动 | 无人记得时复发；无承诺约束 | 作为本次动作执行，但不足以闭环 |
| **b. 反转默认分支** | 把默认分支改为 dev | 访客立刻看到最新 | ① 所有外部链接/badge/PyPI 元数据指向要逐一重估；② 破坏"main=发版"架构一致性；③ PyPI 从 dev 发 beta，访客把 beta 当稳定版 | 违反"架构一致性优先"，弃 |
| **c. 回并 + 机制（推荐）** | 文档/治理修复类改动在合并 dev 时同步落 main；写入 BRANCHING.md 契约 | 保留双分支模型；访客可见面收敛；可检验 | 需要维护者执行纪律；自动 workflow 有回写权限风险 | 推荐 |

选择 c 的理由：**架构一致性**（现有模型是 dev 集成 + main 发版，反转默认分支等于重定义分支语义）优于**改动量最小**。b 案即使在操作上可行，也让"beta 版当作稳定版"的对外语义更混乱。

### D2 回并范围：只回并"纯修复型"文件，逐文件判断

文件是否回并按内容判断，不按批次。判断标准（写入 BRANCHING.md）：
- 该文件在 dev 上的改动是否**只含**对外事实性纠错（版本声明、错误描述、链接修正），且不依赖 dev 上未发布的功能/未合并的 change。
- `SECURITY.md` 符合：#97 的修复是纯版本表述纠错。回并方式：以 dev 版本为准整文件替换（内容在 main 上单独 commit，不用 cherry-pick——main 与 dev 已分叉，cherry-pick 会引入冲突噪声）。
- README 正文重写**不回并**：它捆绑了功能叙述与新特性描述，等价于发布 dev 的全部文档工作,应随发版整体下发。

### D3 可见性契约机制：文档承诺 + 检查命令，暂不建自动 workflow

- `docs/BRANCHING.md` 定义：访客可见面清单（README / README.zh / SECURITY.md / 治理文件 / LICENSE）、"dev 上修对外文档 → 同一发布周期内 main 必须可见"、以及 drift 检查命令（`git diff origin/main...origin/dev -- README.md README.zh.md SECURITY.md LICENSE*` 的输出只允许含"随版本发布的内容"）。
- 自动回并 workflow（Issue 上有 fix-release-version-continuity 先例可参考）：列为后续可选项。原因：经 pre-commit hook 的 `GITHUB_TOKEN` 回写 main 需要绕过 `lock_branch: true` 的分支保护，权限暴露面比收益大；纯文档回并频率低，人工执行 + 契约文档足够。
- 后续所有 change（readme-first-screen 等）的对外文档 PR：按此契约，其"事实纠错"部分（如测试数量、SVM 状态描述）由维护者按契约决定是否同期上 main。

### D4 SECURITY.md 回并方式

以 dev 版本整文件替换 main 版本（dev 为正确版本，#97 已确认）。dev 文件本身不再改动。次序：先 PR 进 dev（本 change 的主体），合并后维护者在 main 上执行同步（main 的 SECURITY.md 换成 dev 版），或者直接由本 change 的实现工作流在 main 上完成。

## Risks / Trade-offs

- [回并后 main 与 dev 的 SECURITY.md 若再各自演化，又出新分叉] → BRANCHING.md 明确"SECURITY.md 以 dev 为唯一编写点，main 只接收同步"；drift 检查命令把该文件列入常查清单。
- [自动回并 workflow 被推迟，承诺靠人执行] → 在 BRANCHING.md 的契约里把检查方法写成一条可粘贴执行的命令，降低执行成本；issue #107 保持 open 直至机制验证过一个真实发布周期。
- [main 与 dev 的 README 差异长期存在，访客在 main 看到的"最新版 README"其实是 0.9 时代的] → 属于 D2 的既定取舍：README 主体重属发布内容，随发版下发。BRANCHING.md 说明这一点，避免被误判为漏改。
- [Windows 工作树上直接操作 origin/main] → 实现阶段用独立分支（如 `fix/main-security-version-sync`）从 main 切出，PR 入 main，不直接 push。

## Migration Plan

1. 本 change 的代码侧：新增 `docs/BRANCHING.md` + CONTRIBUTING/README 互链小节，PR → dev（正常流程，会触发 beta 发版，无功能影响）。
2. main 侧同步：从 `origin/main` 切 `sync/security-version-table` 分支，将 `SECURITY.md` 替换为 dev 版本，PR → main。
3. 验证：在 main 上抽检 SECURITY.md 无版本号残留；执行 drift 检查命令记录输出。
4. 回滚：两处均为文件级 revert，无行为影响。

## Open Questions

（无——三案取舍已在 D1 完成；自动回并是否立项留给维护者在 issue #107 评审时决定，不影响本次任务拆分。）
