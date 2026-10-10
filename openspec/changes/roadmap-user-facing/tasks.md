# roadmap-user-facing 任务清单

## 1. ROADMAP 重写（issue #118 第 1、3 条）

- [ ] 1.1 考据 Now 区：扫 `openspec/changes/` 非 archive 目录 + `CHANGELOG.md`
      `[Unreleased]`，列出真正"进行中/已合并未发版"的能力项
      （验证：Now 条目每条能指出其 change/issue 来源）
- [ ] 1.2 起草 Next/Later 区 4~6 条用户可感知项：跨平台一致性、调度节拍
      （cron / 非 `delay_time` 轮询）、OpenTelemetry 导出、Web 框架生命周期集成、
      指标链路接通、Python 门槛（#124）——每条三字段
      （验证：逐条自查"使用者会因此多做到什么？"能回答）
- [ ] 1.3 重写 `docs/contributing/roadmap.md`（Now/Next/Later、每条 ≤3 行、
      顶部反链 maintainer-backlog；删除全部 2024 商业叙事/过期里程碑）
      （验证：页内无"企业版/云服务/Stars 目标/行动建议"段落）

## 2. maintainer-backlog（issue #118 第 4 条）

- [ ] 2.1 扫当前 open issue，按类别（打包规范/安全供应链/可发现性/流程合规/工程债）
      建 `docs/contributing/maintainer-backlog.md`，条目 = issue 链接 + 一句话 +
      快照日期
      （验证：#118 里点名的内部项（scorecard、分支保护、uv.lock 等）在表中有对应行）

## 3. business-plan 修订（issue #118 第 2 条）

- [ ] 3.1 `docs/internal/business-plan.md` 去冲突："生产就绪/完善/自动故障检测"
      加限定或删除；`ROADMAP.md` 死链改指向 `contributing/roadmap.md`
      （验证：grep 逐条核对；文档仍留在 docs/internal/ 不进站点构建）

## 4. 索引与构建回归

- [ ] 4.1 `docs/contributing/README.md` 表格加"维护者待办"行
      （验证：两个入口齐全）
- [ ] 4.2 `mkdocs build`（严格模式若可用）无 dead link
      （验证：构建输出 0 error）
- [ ] 4.3 门禁：ruff /（docs 变更不触发 mypy 范围）/ 全量 pytest 不回归
      （验证：输出留痕）
- [ ] 4.4 `openspec validate roadmap-user-facing --strict` 0 警告；tasks 全勾；
      提交（`Closes #118`）+ md5 核对
      （验证：与备份差异仅限预期文件）
