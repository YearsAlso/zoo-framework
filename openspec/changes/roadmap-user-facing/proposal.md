# 提案：roadmap-user-facing —— ROADMAP/BUSINESS_PLAN 改为用户可见能力路线图

对应 issue：YearsAlso/zoo-framework#118（P1，exposure/credibility）

## Why（为什么做）

`docs/contributing/roadmap.md`（364 行）与 `docs/internal/business-plan.md`（398 行）
停留在 2024-02 写就的商业叙事，与文档站的既有口径（README、mkdocs.yml、benchmark.md）
存在三处矛盾，访客点进"路线图"读到的印象是"维护者自己的流程实验"：

1. **把内部债务当路线图**：roadmap.md 的 Phase 1"立即行动"是"测试覆盖率 80%、
   修复 CI 测试错误、发布 v0.2.0"——全是维护者待办，当前仓库 21 个 open issue 里
   使用者可感知的能力项一个没写；公开 backlog 本身应是招募材料。
2. **与 README 冲突的信任声明**：roadmap.md/auth business-plan.md 仍含
   "SVM 状态监控（自动故障检测未生效）"以"核心优势"面貌出现（roadmap.md:14）、
   "生产就绪 已验证"五星评级与"有实际商业项目支撑"（roadmap.md:67）、
   "完善了日志和监控"（business-plan.md:59）——README 限制表明确写着
   "指标链路未接通，`get_health_report()` 恒返回 `execute_count: 0"`（README.md:259）。
3. **2024 年时间线已过期**：里程碑表写"v1.0 稳定版 2024.06、企业版 2025.01"，
   今天是 2026-10，全部里程碑均已过期且无一兑现；企业版/云服务商业模式
   与实际维护状态（单人维护、无商业化动作）不符。

现状定位：roadmap 被文档站收录（mkdocs.yml:96"路线图"），入口可见；
business-plan 已在 `docs/internal/`（不发布，mkdocs.yml:118 注释明确排除）。

## What Changes（变更什么）

### 1. 重写 `docs/contributing/roadmap.md` 为用户可见能力路线图

- 结构 Now / Next / Later，每项 ≤3 行，必须回答"使用者会因此多做到什么？"
- 每条标注：影响谁 / 当前状态 / 衡量方式（怎么知道做完了）
- Now 区从实际 in-flight 与已定方向考据，Next/Later 区起草 4~6 条用户可感知项，方向覆盖 issue #118 列举的：
  跨平台一致性、可插拔调度节拍（cron / 非固定 `delay_time`）、OpenTelemetry 导出、
  Web 框架（FastAPI/Django）生命周期集成、健康监控指标链路接通、Python 版本门槛（#124）。
- 内部债务项（CI 修复 #144、类型注解 #141、native CI #129、安全收口 #121 等）
  **不列入** roadmap，移入新建的 `docs/contributing/maintainer-backlog.md`。
- roadmap 顶部一句话说明"维护者待办、流程类工件不在此列，见 maintainer-backlog.md"。

### 2. `docs/internal/business-plan.md` 降级（保留但去冲突）

- business-plan 已位于 docs/internal/ 不发布，**保留**（维护者决策参考仍有价值）；
- 但其"商业价值"表述在仓库内部仍可能被检索到（docs/** 全文检索、GitHub 代码搜索），
  因此shall去除/修正与 README、roadmap 冲突的三类表述：
  "生产就绪"绝对化用语 → 以 zoo-bench / docs/benchmark.md 为证据来源的限定表述；
  "健康监控告警（完善）"→ 注明指标链路未接通现状；
  "Roadmap(ROADMAP.md)" 死链 → 指向 docs/contributing/roadmap.md。
- 不删档（内容为维护者视角的商业可行性初稿，删除即丢失决策记录）。

### 3. 新建 `docs/contributing/maintainer-backlog.md`

- 按类别归档当前 open issue 中的内部债务项（exposure/credibility/docs-consistency
  的文档线、standards 的打包线、ops 类），每条注明 issue 编号；
- ROADMAP 顶部反链接它。

### 4. 索引同步（机械一致性）

- `docs/contributing/README.md` 的"路线图"一行补上 maintainer-backlog 入口；
- `mkdocs.yml` 不动结构（"路线图"路径不变，仅内容换血）；
- README / README.zh.md 已经链接 `docs/contributing/roadmap.md`，路径不变。

## Impact（影响面）

- 重写：`docs/contributing/roadmap.md`（整页换血，364 行 → 约 100 行）
- 新建：`docs/contributing/maintainer-backlog.md`
- 修订：`docs/internal/business-plan.md`（去冲突用语 + 修死链，约 ±10 行）
- 修订：`docs/contributing/README.md`（表格加一行）
- 不动：mkdocs.yml 导航、README 双语链接、`docs/internal/optimization-plan.md`
- 纯文档变更：不触发 release（paths 过滤器不含 docs/**）；零代码影响；
  mkdocs build --strict 需复跑（dead-link 检查）。

## 能力归属（spec delta 落点）

新能力 `docs-roadmap`：两个 Requirement——
(1) 用户可见性约束（每条 roadmap 项写"你能做什么了"，禁内部债务混入）；
(2) 双文档分工（roadmap = 用户可见能力三档，maintainer-backlog = 维护者债务台账）。
