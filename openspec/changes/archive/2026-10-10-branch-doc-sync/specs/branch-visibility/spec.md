# branch-doc-sync 规格增量 · branch-visibility

## Purpose

定义"访客可见面"契约：对外文档与治理文件在默认分支 (`main`) 上的可见性与不漂移规则，使 dev 分支上的对外事实性修复在可预期时间内对访客可见，并能通过一条可执行检查验证。

## ADDED Requirements

### Requirement: 访客可见面文件清单

仓库 SHALL 在 `docs/BRANCHING.md` 中维护一份「访客可见面」文件清单（初始为：`README.md`、`README.zh.md`、`SECURITY.md`、`LICENSE`、`CODE_OF_CONDUCT.md`、`SECURITY.txt` 类治理文件），清单内每一项 MUST 对应孤立的职责描述——该文件在 main 分支上的内容 MUST 与 dev 分支上"最近的对外事实性状态"一致。

#### Scenario: 清单存在且每项有职责说明
- **WHEN** 阅读 `docs/BRANCHING.md`
- **THEN** 能找到访客可见面文件清单，且每项文件旁有一句话说明其对外可见性要求

### Requirement: 对外事实性修复的可见性时限

当对外文档或治理文件在 `dev` 上完成事实性修复（版本声明、错误描述、支持策略等，不依赖 dev 独有功能）时，该修复 MUST 在**同一发布周期内**出现在 `main` 分支上。不符合条件的差异（随版本发布的功能类内容，如 README 特性叙述）MUST 在 `docs/BRANCHING.md` 中被明确声明为"发布随发版下发"，不得被误判为漏改。

#### Scenario: SECURITY.md 版本表修复后 main 可见
- **WHEN** `SECURITY.md` 的支持版本表在 dev 上改为"不随版本漂移"的写法
- **THEN** 同一发布周期内 `main` 分支上的 `SECURITY.md` 不再出现旧版本号声明（如 `0.5.3-beta`），且其支持线以"PyPI 最新 minor 线"表述，不含具体版本号

#### Scenario: 功能类差异不误判
- **WHEN** `main` 与 `dev` 的 README 正文存在大段差异（dev 的 README 重写未发布）
- **THEN** `docs/BRANCHING.md` 明确该差异属于"随发版下发"类别，不被当作违反可见性契约

### Requirement: 漂移检查方法可执行

`docs/BRANCHING.md` SHALL 提供一条可直接粘贴执行的 drift 检查命令（基于 `git diff origin/main...origin/dev -- <访客可见面文件>`），并说明输出如何解读：命中"事实性纠错"即违反契约，命中"发布随发版内容"则正常。

#### Scenario: 检查命令可运行且结果可判读
- **WHEN** 维护者在任意 clone 上执行该文档给出的检查命令
- **THEN** 命令成功运行，且文档中的判读规则能明确区分"违反后果"与"正常差异"

### Requirement: 治理文件的单一编写点

访客可见面中的治理文件（`SECURITY.md` 等）SHALL 以 `dev` 为唯一编写点，`main` 只接收同步；其内容 MUST NOT 在 main 上独立演化出 dev 没有的修改。

#### Scenario: main 侧不产生独立演化
- **WHEN** 需要修改 `SECURITY.md` 的报送流程或支持策略
- **THEN** 编辑发生在 dev，随后按可见性契约同步到 main；不存在只存在于 main 的内容差异
