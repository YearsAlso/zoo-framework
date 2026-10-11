# changelog-backfill 任务清单

## 1. CHANGELOG 回填（issue #117 第 1 条）

- [x] 1.1 `[0.8.1-beta]` ~ `[0.8.4-beta]`、`[0.9.0]`、`[0.9.1-beta]`、`[0.9.2-beta]`、
      `[0.10.0]`、`[0.10.1-beta]` ~ `[0.10.6-beta]` 共 13 段新条目（日期 = tag
      creatordate；每版主题 + 分类条目 + 来源标注）（验证：`grep -c "^## \["` 与
      已发布版本对照、差异处可解释）
- [x] 1.2 `[Unreleased]` 的 #73/#72/#82 条目迁移至 `[0.9.1-beta]` / `[0.9.2-beta]`，
      Unreleased 清为空节（验证：三个主题各只在一版出现）
- [x] 1.3 交叉发布处理：0.8.1~0.8.4 与 [0.9.0] 之间、0.10.0 与 [0.9.2-beta] 之间用
      交叉引用（验证：无内容漂移重复）
- [x] 1.4 BREAKING 条目（gevent/cage/worker/validation/event:sleep）带迁移说明或
      锚定 docs/MIGRATION.md（验证：逐条 grep）
- [x] 1.5 历史版本表补充「未回填」标注（0.5.x–0.7.1）（验证：表内每行有去向）

## 2. release note 模板（issue #117 第 2 条）

- [x] 2.1 新增 `docs/RELEASE_PROCESS.md`：四段模板（主题/使用者可见变化/破坏性变更
      与迁移/已知问题）+ 内部重构规则 + 发版前先写 CHANGELOG 的操作顺序
      （验证：文件存在且四段齐全）

## 3. 生成链路（issue #117 第 3 条）

- [x] 3.1 新增 `scripts/notes_from_changelog.py`：抽 `## [版本]` 节，exit 非 0 表示
      无节（验证：对已有版本抽成功、对无节版本报错）
- [x] 3.2 release.yml `Generate Changelog` 步骤改为「脚本优先 + git log 回退」；
      body 加四段骨架（验证：yaml 语法 + 步骤逻辑 review）
- [x] 3.3 不碰 OIDC / 签名 / tag / back-merge / 版本算术（验证：git diff 范围仅此步）

## 4. 回归与验证

- [x] 4.1 门禁：ruff（py 脚本）/ mypy / 全量 pytest 全绿（验证：输出留痕）
- [x] 4.2 `openspec validate changelog-backfill --strict`（验证：0 警告）
- [x] 4.3 提交（`Closes #117`）+ md5 核对（验证：与备份差异仅限预期文件）
