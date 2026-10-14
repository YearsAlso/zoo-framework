## MODIFIED Requirements

### Requirement: release 正文 SHALL 有固定四段模板并由 CHANGELOG 驱动

每个 GitHub release 的正文 SHALL 包含：一句话主题 / 使用者可见的变化 / 破坏性变更与
迁移 / 已知问题（无则写「无」）；内部重构 MUST NOT 出现在使用者可见段。正文的主内容
SHALL 由该版本的 `CHANGELOG.md` 段落抽取生成（`scripts/notes_from_changelog.py`），
抽取失败时 SHALL 回退到提交列表并在正文标注「未整理」。

回退路径产出的正文 MUST 在写入 `$GITHUB_OUTPUT` 前保证**以换行结尾**：多行输出用
`key<<EOF ... EOF` 语法传递，正文末字节不是换行时定界符会被粘到末行上，GitHub 报
`Invalid value. Matching delimiter not found`，该步骤失败、其后的 `Create GitHub
Release` 被跳过——结果是 PyPI 上已发布而 GitHub Releases 里缺这一版。该补齐 MUST NOT
依赖正文生产者各自的换行习惯：`git log --pretty=format:` 不带尾换行，而 `head -20` 只在
真的截断时才顺带补上换行，故提交数少的区间必现。

#### Scenario: 模板文档存在
- **WHEN** 打开 `docs/RELEASE_PROCESS.md`
- **THEN** 含四段模板 + 「内部重构不进使用者可见段」规则 + 「发版前先写 CHANGELOG」
  的操作顺序

#### Scenario: 抽取脚本行为
- **WHEN** 对一个 `CHANGELOG.md` 里有节的版本执行
  `python scripts/notes_from_changelog.py <版本>`
- **THEN** stdout 输出该节全文，exit 0；对没有节的版本 exit 非 0（不静默输出空）。
  release.yml 的 body 生成 SHALL 优先脚本、失败回退提交列表

#### Scenario: 提交数少的版本仍建出 Release
- **WHEN** 某次发布的 tag 与上一个 tag 之间提交很少（走提交列表回退，且 `git log
  --pretty=format:` 的输出不带尾换行）
- **THEN** `Generate Changelog` 步骤以成功结束，正文含提交列表与「未整理」标注
- **AND** `$GITHUB_OUTPUT` 里的定界符独占一行（可被 `key<<EOF ... EOF` 语法解析）
- **AND** 其后的 `Create GitHub Release` 步骤被实际执行（不为 skipped）
