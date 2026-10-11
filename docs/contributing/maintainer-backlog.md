# 维护者待办台账

这一页是**维护者自己的活**——对使用者没有直接感知、但影响可信度、合规与开发者体验
的债务与整改项。**使用者可感知的能力方向在 [路线图](roadmap.md)**，两边不重复登记。

> **口径**：issue tracker 是唯一真源，本页只是索引——每条只写一行（编号 + 一句话），
> **不复制 issue 正文**，避免双源漂移。对应 issue 关闭后，请把该行删除或移入下方
> "已完成"清单。
>
> **快照日期**：2026-10-10（`gh issue list --state open` 全量核对）。

## 打包与规范

| 项 | 一句话 | 状态 |
|---|---|---|
| [#119](https://github.com/YearsAlso/zoo-framework/issues/119) | 迁移到 PEP 639 许可证写法，补 CITATION.cff 与 SBOM | open |
| [#141](https://github.com/YearsAlso/zoo-framework/issues/141) | 补齐 40 处公开 API 签名缺失的类型注解，让 `mkdocs --strict` 与 mypy 门禁真正生效 | open |
| [门禁放宽建议](../CONTRIBUTING_MAINTAINER.md#gate-suggestions-zh) | 覆盖率下限 30%／mypy 范围／文档站 strict 三条**建议**调整，均标注"尚未生效"、未动 `.github/workflows/` | 建议，无 issue |

## 安全与供应链

| 项 | 一句话 | 状态 |
|---|---|---|
| [#121](https://github.com/YearsAlso/zoo-framework/issues/121) | 收口 #89–#95 安全项的实际生效状态，输出 SECURITY_MODEL.md | open |
| [#129](https://github.com/YearsAlso/zoo-framework/issues/129) | 原生扩展无 CI、无 wheel、未启用 abi3、PyPI 404——go 结论交付不到使用者手上 | open（P0） |

## 合规与治理材料

| 项 | 一句话 | 状态 |
|---|---|---|
| [#120](https://github.com/YearsAlso/zoo-framework/issues/120) | 补齐 GOVERNANCE／MAINTAINERS／ADOPTERS／security.txt（OpenSSF 徽章前置材料） | open |

## 可发现性与贡献者体验

| 项 | 一句话 | 状态 |
|---|---|---|
| [#122](https://github.com/YearsAlso/zoo-framework/issues/122) | 新增 llms.txt／AGENTS.md，README 补自然语言 FAQ（AI 检索可发现性） | open |
| [#123](https://github.com/YearsAlso/zoo-framework/issues/123) | 打开贡献路径：拆分 CONTRIBUTING、免流程通道、5 个真 good-first-issue | open |

## 工程债与开发者体验

| 项 | 一句话 | 状态 |
|---|---|---|
| [#144](https://github.com/YearsAlso/zoo-framework/issues/144) | `test_worker_wakes_on_producer_event` 在 macOS 间歇失败，制造假红灯 | open（P1） |
| [#131](https://github.com/YearsAlso/zoo-framework/issues/131) | `zfc --worker` 在项目外静默成功，留下游离 `workers/` 并返回 0，违反自身契约 | open |
| [#130](https://github.com/YearsAlso/zoo-framework/issues/130) | 原生收益包络回归：门槛在 10.3 字节，当前写 ≥21，建议补测 10／12／16B | open |
| [#112](https://github.com/YearsAlso/zoo-framework/issues/112) | `zfc --worker` 生成的类名未转 PascalCase（如 `My_TaskWorker`） | open |

## 总纲与仓库设置

| 项 | 一句话 | 状态 |
|---|---|---|
| [#125](https://github.com/YearsAlso/zoo-framework/issues/125) | 吸引力审计总纲与工作队列（含 GitHub 仓库设置类运营动作：Topics／About 等） | open（元 issue） |

## 已完成（本分支在途，合入 `main` 后自动关闭）

| 项 | 说明 |
|---|---|
| [#114](https://github.com/YearsAlso/zoo-framework/issues/114) | 文档自相矛盾清理 + 文档一致性测试 |
| [#115](https://github.com/YearsAlso/zoo-framework/issues/115) | bumpversion 版本字段说谎 + uv.lock 陈旧 |
| [#116](https://github.com/YearsAlso/zoo-framework/issues/116) | `example/` 残留与子模块说明 |
| [#117](https://github.com/YearsAlso/zoo-framework/issues/117) | CHANGELOG 回填与 release note 模板 |
| [#118](https://github.com/YearsAlso/zoo-framework/issues/118) | 本页与路线图的拆分（本变更） |
