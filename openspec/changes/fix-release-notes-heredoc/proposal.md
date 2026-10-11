# 提案：fix-release-notes-heredoc —— release 正文写入 `$GITHUB_OUTPUT` 前补齐尾换行

## Why

v0.12.0（main 的正式版）发布**半途而废**：`Publish to PyPI` 成功、`Generate Changelog`
失败，其后的 `Create GitHub Release` 与 `Notify Success` 被跳过——PyPI 上有
[0.12.0](https://pypi.org/project/zoo-framework/0.12.0/)，GitHub Releases 里没有
`v0.12.0`（`gh release view v0.12.0` → release not found）。运行日志原文：

```
##[error]Unable to process file command 'output' successfully.
##[error]Invalid value. Matching delimiter not found 'EOF'
```

根因：`Generate Changelog` 用 `$GITHUB_OUTPUT` 的 `key<<EOF ... EOF` 多行语法回传正文，
而回退路径的正文由 `git log --pretty=format:"- %s (%h)"` 产出——**该格式不带尾换行**。
末字节不是换行时 `cat` 会把 `EOF` 粘到末行上，定界符不再独占一行，GitHub 直接报错。
本机复现（1 个提交的区间，文件 127 字节、末字节为 `)`）：

```
changelog<<EOF
- chore(release): bump version to 0.12.0 [skip ci] (21b1385)EOF
```

**为什么同一份 `release.yml` 在 v0.11.13-beta 上却是成功的**：那条命令是
`git log ... | head -20`，而 `head -20` **只在真的截断时**才顺带补上换行——0.11.13-beta
的区间有 21 个以上提交（自环期间积累的），0.12.0 的区间只有一个 bump 提交，于是前者侥幸
躲过、后者必现。自环终止后每次发布的区间都会变短，**后续每一次走回退路径的发布都会这样
失败**。

## What Changes

- `release.yml` 的 `Generate Changelog` 步骤：在写多行输出之前统一补齐一次尾换行
  （`printf '\n' >> release_notes.md`），不再依赖正文生产者各自的换行习惯；注释写明根因与
  实测证据（v0.12.0）。
- 机械校验：`tests/test_doc_consistency.py` 新增用例，**真的执行**该步骤的 `run` 块
  （`git` / `python` 用 shell 函数打桩以迫使走回退路径，`git log` 桩按 `--pretty=format:`
  的真实行为输出不带尾换行），断言写出的 `$GITHUB_OUTPUT` 能被 `key<<EOF ... EOF` 解析。
- 规格 `changelog-backfill` 的 MODIFIED Requirement：回退路径写出的正文 MUST 以换行结尾；
  补 Scenario「提交数少的版本仍建出 Release」。

## Non-Goals

- 不改发布步骤的顺序（`Publish to PyPI` 在正文生成之前这一现状保留，理由见 `design.md`）。
- 不改回退语义：仍是「找不到 CHANGELOG 段 → 提交列表 + 未整理标注」，仍不加
  `continue-on-error`（"看起来成功但没有正文"与"看起来成功但没有 SBOM"同样不可接受）。
- 不改 `head -20` 的截断行为，不改正文内容。
- 不回填 `CHANGELOG.md` 的 0.12.0 段，也不补建 `v0.12.0` 的 GitHub Release——那属于发布
  记录本身，需人工决定；本变更只保证后续发布不再断在这一步。
- 不引入新的第三方依赖或 action。

## Impact

- `.github/workflows/release.yml`：`Generate Changelog` 步骤 +1 行、注释若干。
- `tests/test_doc_consistency.py`：新增 1 个用例 + 1 个步骤提取辅助函数。
- `openspec/changes/fix-release-notes-heredoc/`：本提案、`design.md`、`tasks.md` 与
  `changelog-backfill` 的 spec delta。
