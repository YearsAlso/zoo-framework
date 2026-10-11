## 1. 回归与实现

- [x] 1.1 在未修改的 `dev` 上增加项目外调用的回归用例；验证非零退出、错误提示和目录快照不变；确认基线因静默成功而失败。
- [x] 1.2 让 Worker 目录解析向父目录查找最近的 `src/main.py`，无入口时在写入前以 `click.ClickException` 失败。
- [x] 1.3 修正入口路径解析，并保留组合创建、项目根与子目录调用行为。
- [x] 1.4 更新现有跨平台路径用例，覆盖缺失入口时拒绝、最近父项目解析及 Worker 目录创建。

## 2. 规格与文档

- [x] 2.1 编写 OpenSpec proposal、design、CLI delta spec 与 tasks，记录选择 `src/main.py` 的理由。
- [x] 2.2 更新 README、CLAUDE.md 和 CHANGELOG 中的 CLI 行为。

## 3. 验证

- [x] 3.1 运行聚焦测试和完整 pytest 套件（维护者复测：1011 passed, 0 skipped）。
- [x] 3.2 运行 Ruff、MyPy、Bandit 及 OpenSpec 严格校验。
- [x] 3.3 检查 diff、文档与测试快照，确认无新增运行依赖；pre-commit 的仓库级格式/lint失败在干净基线上复现（bench `zip()` 的 B905 与现有空白/换行问题）。

## 4. 合入前审查整改

- [x] 4.1 恢复 `resolve_worker_dir` docstring 为英文：它在 `zoo_framework.cli.__all__` 导出面内，`bbf06ae`（变更 `api-docstring-english`）已英文化，本变更曾改回中文。
- [x] 4.2 新增的报错消息改英文：用户可见控制台输出 MUST 为英文，中文消息在 GBK 控制台乱码，且会使该变更的验证门 4.1（raise/log/print 零 CJK）失效。
- [x] 4.3 项目外用例的"零产出"断言补上目录维度：`_snapshot` 原先只登记文件，注入"先建目录再报错"的违规实现时断言仍绿（已实测）。
- [x] 4.4 design.md 显式把 issue #131 第 4 点（`--create` 目标不可创建时抛裸异常栈）列为范围外。
- [x] 4.5 CHANGELOG 条目改中文，补 `（变更 fix-zfc-worker-project-root / #131）` 溯源与 BREAKING 标注。
