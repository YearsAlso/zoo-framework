## 1. 回归与实现

- [x] 1.1 在未修改的 `dev` 上增加项目外调用的回归用例；验证非零退出、错误提示和目录快照不变；确认基线因静默成功而失败。
- [x] 1.2 让 Worker 目录解析向父目录查找最近的 `src/main.py`，无入口时在写入前以 `click.ClickException` 失败。
- [x] 1.3 修正入口路径解析，并保留组合创建、项目根与子目录调用行为。
- [x] 1.4 更新现有跨平台路径用例，覆盖缺失入口时拒绝、最近父项目解析及 Worker 目录创建。

## 2. 规格与文档

- [x] 2.1 编写 OpenSpec proposal、design、CLI delta spec 与 tasks，记录选择 `src/main.py` 的理由。
- [x] 2.2 更新 README、CLAUDE.md 和 CHANGELOG 中的 CLI 行为。

## 3. 验证

- [x] 3.1 运行聚焦测试和完整 pytest 套件（999 passed, 1 skipped）。
- [x] 3.2 运行 Ruff、MyPy、Bandit 及 OpenSpec 严格校验。
- [x] 3.3 检查 diff、文档与测试快照，确认无新增运行依赖；pre-commit 的仓库级格式/lint失败在干净基线上复现（bench `zip()` 的 B905 与现有空白/换行问题）。
