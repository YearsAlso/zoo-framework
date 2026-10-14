# 设计：fix-release-notes-heredoc

## 定位与证据链

| 环节 | 事实（可复跑） |
|---|---|
| 失败现象 | v0.12.0 发布运行 `38142981830` 的 `🚀 发布` 作业：`Publish to PyPI` success，`Generate Changelog` failure，`Create GitHub Release` / `Notify Success` skipped |
| 报错 | `Invalid value. Matching delimiter not found 'EOF'` |
| 正文来源 | 该版本的 CHANGELOG 无条目 → `notes_from_changelog.py` 非零退出 → 回退 `git log --pretty=format:"- %s (%h)" --no-merges \| head -20 > release_notes.md` |
| 为什么末行与定界符相粘 | `--pretty=format:` 的输出**不带尾换行**；`cat release_notes.md >> "$GITHUB_OUTPUT"` 原样落盘，`echo "EOF"` 紧随其后 |
| 为什么 beta 没炸 | `head -20` 只在**真截断**时才顺带补上换行：0.11.13-beta 的区间有 21+ 个提交（自环期积累），0.12.0 的区间只有 1 个 bump 提交 |

复现（本机 1 个提交的区间）：

```
$ git log v0.11.13-beta..v0.12.0 --pretty=format:"- %s (%h)" --no-merges | head -20 > n.md
$ wc -c < n.md → 127     # 末字节 `)`，无换行
$ { echo "changelog<<EOF"; cat n.md; echo "EOF"; } → "- ...(21b1385)EOF"
```

## 方案选择

| 方案 | 收益 | 风险 | 改动量 |
|---|---|---|---|
| **A（采用）写出前补齐尾换行**：`printf '\n' >> release_notes.md` | 与"正文如何生成"解耦——将来换任何写入方式都受保护；正文内容与回退语义不变；一行 | 正文末尾多一个空行（markdown 渲染无害） | `release.yml` 1 行 + 注释 |
| B 在 `--pretty=format:` 格式串末尾加 `%n` | 从源头保证换行 | 只覆盖这两条 `git log`；将来换了写入方式仍会复发 | 2 行 |
| C 把该步骤的 `run` 块抽成仓内脚本（`scripts/release_notes.py`） | 逻辑可被 pytest 直接调用（与 `scripts/next_version.py` 同形） | 改动面超出一个缺陷的修复范围；`$GITHUB_OUTPUT` 的写入位置、步骤语义都要动 | 新增脚本 + `release.yml` 若干行 |

选 A（B 非必需——A 覆盖全部写入路径），理由按优先级：**架构一致性**（`$GITHUB_OUTPUT` 的
写入仍留在 shell 里，不为一个缺陷引新脚本与新的入口）、**业务连续性**（正文内容、回退语义、
步骤顺序皆不变）、**改动量最小**（1 行）三者同时满足。

## 为什么不动发布步骤的顺序

`Publish to PyPI` 排在正文生成之前，所以这一步失败会留下"已上传 PyPI、没有 GitHub
Release"的半成品状态。把正文生成挪到上传之前能避免它，但它改变发布链路的时序语义（失败
时 tag 已存在、版本号已消耗，下一次发布如何续上需要一并设计），属于另一次变更的决策范围。
本变更只消灭这一步的失败本身，不夹带顺序调整。

## 验证策略

- **行为验证**：用例不读 YAML 文本下结论，而是把该步骤的 `run` 块**真的执行**一遍
  （`git` / `python` 打桩：`python` 失败迫使走回退路径，`git log` 按 `--pretty=format:` 的
  真实行为输出不带尾换行），再断言写出的 `$GITHUB_OUTPUT` 能被多行语法解析、正文行未丢。
- **牙齿验证**：删掉 `printf` 行（即修复前的线上状态）→ 用例变红，输出里能直接看到
  `'- fix(zfc): fake commit (abc1234)EOF'`；按 md5 逐字节还原后复跑通过。
- **真实验证只能等下一个 tag**：本变更触及 `release.yml`，合入后会触发一次版本号 PR，其合并
  产生的 tag 才会跑完 `Generate Changelog` → `Create GitHub Release`（那同时也是
  `fix-sbom-out-of-dist` 之后的又一次真实发布）。在那之前**不得声称发布链路已修好**。
