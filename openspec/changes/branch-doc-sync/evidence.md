# branch-doc-sync 证据与 PR 素材

> 本文件存档 tasks 1.1 / 1.2 / 4.x 的命令原始输出，PR 描述直接引用此处内容。

## 1.1 分支分歧量化（实测于 apply 阶段，HEAD e93962e 的 worktree）

```
$ git rev-list --count origin/main..origin/dev
52

$ git rev-list --count origin/dev..origin/main
3

$ git diff --stat origin/main...origin/dev -- "*.md" | tail -3
 openspec/specs/adaptive-scheduling/spec.md         |  87 +++++
 openspec/specs/native-task-execution/spec.md       |  74 +++++
 29 files changed, 1982 insertions(+), 372 deletions(-)
```

注：提案/设计阶段测得 29 commit，apply 时已增长到 52——dev 持续前进，正是"漂移会自行变大"的直接证据。

## 1.2 main 上访客可见的错误清单

| 文件 | main 上现状 | 处置 |
|---|---|---|
| `SECURITY.md` | 支持版本表声明 `0.5.3-beta` / "latest 0.5.x"；dev 版（#97 修复）已改为不随版本漂移的写法 | **随本 change 回并**（任务 3.1） |
| `README.md` / `README.zh.md` | dev 上已完成重写（首屏定位、特性表），且包含尚未发布功能的叙述 | **随发版下发**（bridge: design.md D2，不回并） |
| `CONTRIBUTING.md` | main 与 dev 内容一致（不在 diff 名单中） | 无需处理 |
| `LICENSE` / `CODE_OF_CONDUCT.md` | 不在 diff 名单中 | 无需处理 |

## 4.2 drift 检查输出（BRANCHING.md 命令，apply 阶段实测）

```bash
$ git diff origin/main...origin/dev -- README.md README.zh.md SECURITY.md LICENSE CODE_OF_CONDUCT.md CONTRIBUTING.md --stat
```

结果（63.4KB 输出，归档于会话临时文件）逐文件判读：

| 文件 | 差异量 | 判读 |
|---|---|---|
| `SECURITY.md` | 两段（英文半 + 中文半，各 ~15 行）：`0.5.3-beta` / "latest 0.5.x" → 不漂移表述 | **违反规则 3**（治理文件在 main 上有 dev 之外的旧演化）→ 已决策方式 A：随下次 dev→main 发版下发 |
| `LICENSE` | 无差异 | ✅ 合规 |
| `CODE_OF_CONDUCT.md` | 无差异 | ✅ 合规 |
| `CONTRIBUTING.md` | 无差异（apply 前一致；apply 后 dev 侧新增 BRANCHING 互链，属规则 1 事实性修复，随本 change 合入 dev，下次发版下发） | ✅ 合规 |
| `README.md` / `README.zh.md` | 大段（双语拆分、徽章、定位重写、架构图） | 规则 2 豁免：随发版下发的功能类内容，非事实性修复漏改 |

结论：**唯一违反项为 SECURITY.md，处置路径已定（随发版下发）**；其余访客可见面文件均合规。下次发版合并进 main 后重跑本命令，`SECURITY.md` 差异应清零，届担任务 3.1 的验证（`git show origin/main:SECURITY.md` 无 `0.5.3-beta`）一并完成。
