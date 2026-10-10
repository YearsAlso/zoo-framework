# 发布流程 / Release Process

本页是发版时的操作说明。发布机制（谁扣动扳机、版本号怎么算、签名与 PyPI 上传）
见 `CHANGELOG.md` 底部「版本号约定」与 `.github/workflows/release.yml`——本页只讲
**release 正文怎么写**。

## release 正文的四段模板

每个 GitHub Release 的正文 SHALL 按以下四段组织（由 release workflow 从
`CHANGELOG.md` 自动抽取该版本段生成，骨架见 release.yml）：

```markdown
## 🎉 Release <版本号>

**主题**：<一句话——这个版本让使用者能做什么新事情 / 修了什么>

### 📋 使用者可见的变化
（Added / Changed / Fixed / Removed 中**对使用者有感**的条目，受众照抄 CHANGELOG）

### ⚠️ 破坏性变更与迁移
（有的话逐条列出 + 迁移说明；**没有就写"无"**——空缺也是信息，别让人猜）

### 📝 已知问题
（有没有著名的、本版本尚未处理的坑；没有就写"无"）

### 📦 安装        ← workflow 自动追加，不需手写
### 📚 文档        ← workflow 自动追加，不需手写
```

## 规则

1. **内部重构不写进使用者可见段**。若无行为影响，它最多以一句话出现在主题段或
   Changed 段（保持与 CHANGELOG 相同口径：维持者视角的一句话即可），且 MUST NOT
   占据正文主体——订阅了 release feed 的读者只关心"我能做什么新事"。
2. **BREAKING 必须显式标注**并给迁移说明（或锚定 `docs/MIGRATION.md` 对应小节）。
   破坏性变更藏在正文第三屏就等于没有标注。
3. **发版前先写 CHANGELOG**。放发版当天临时拼正文是本仓库曾经的实际状态
   （每个 release 正文只有一句 `Release vX.Y.Z`，issue #117）——正确顺序是：

   1. 在 `CHANGELOG.md` 写好该版本的 `## [版本号] - 日期` 段（或确认
      `[Unreleased]` 内容已就绪并重命名）；
   2. 合并 bump PR —— workflow 打 tag 触发发布；
   3. `scripts/notes_from_changelog.py <版本号>` 会从 CHANGELOG 抽出该段，生成正文。
      **该脚本找不到对应段时以非零退出**：workflow 回退到提交标题列表并在正文标注
      「未整理」——看到它就该知道哪一步被跳过了。
4. 交叉发布的 beta（同一条内容先 beta 后正式版）：正式版段写全，beta 段用交叉
   引用指向正式版段——release 正文同理，不重复叙述两遍。
