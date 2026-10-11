# repo-hygiene Spec Delta — repo-hygiene

## ADDED Requirements

### Requirement: 版本声明 MUST 只剩一条真源链，死配置不得留驻

仓库的版本事实 SHALL 只由发布流程维护的三处声明承载（`pyproject.toml` 的
`[project].version`、`.env` 的 `VERSION`、`[tool.release]` 无关的
`zoo_framework/__init__.py.__version__`），三者 SHALL 一致；不被发布流程使用的
版本工具配置（bumpversion 及其 dev 依赖 `bump-my-version`）MUST NOT 以"可用工具"
的形态留驻——零使用的配置段 MUST 删除而不是修正为真实值，避免下次发版时被
误当作流程的一部分。

#### Scenario: bumpversion 死段被删除
- **WHEN** `grep -n "current_version" pyproject.toml`
- **THEN** 零命中；dev 依赖里不再有 `bump-my-version`

#### Scenario: 三处版本声明一致
- **WHEN** 同时读取 `pyproject.toml` 的 `version`、`.env` 的 `VERSION` 与
  `zoo_framework.__version__`
- **THEN** 三者逐字一致（`0.10.6-beta`），并随每次发布由 release.yml 一并改写

### Requirement: 依赖 MUST 只有一个真源，lock 文件的可用性承诺 MUST 有实测背书

`pyproject.toml` SHALL 是依赖的唯一真源；并列的依赖清单文件（`requirements*.txt`）
MUST NOT 存在——若其承载的内容与 extras 不一致，就是第二真源，MUST 删除并把
安装指引统一到 extras。`uv.lock` SHALL 与 `pyproject.toml` 一致（`uv lock --check`
通过），且 SHALL 经隔离干净环境验证 `uv sync --extra dev --extra docs` 装齐
pytest / ruff / mkdocs 全套工具链。

#### Scenario: uv sync 在干净环境可用
- **WHEN** 在不继承任何现有环境的干净 venv 里执行 `uv sync --extra dev --extra docs`
- **THEN** pytest、ruff、mkdocs 等开发工具全部装入并能运行；全量 pytest 通过
  （可选原生扩展缺席导致的 skip 不算失败）

#### Scenario: 文档警告与实况一致
- **WHEN** 读者在 README / CONTRIBUTING / CLAUDE.md 中查找 uv 的使用指引
- **THEN** 看到的是一句与实况一致的正常说明（`uv sync` 可安全使用），而非
  "lock 陈旧会毁环境"的陈旧警告；`requirements-dev.txt` 在全库零引用

#### Scenario: lock 与 pyproject 保持一致
- **WHEN** `uv lock --check`
- **THEN** 通过（lock 覆盖 pyproject 声明的全部依赖，包括 optional extras）
