# repo-hygiene 设计

## 决策记录

### 1. uv.lock：重新生成并实测验证（而非删除）

issue #115 给出二选一：修到一致，或删掉 lock 只留 pip。选择**重新生成 `uv.lock` 并放弃"陈旧警告"架子**。理由：

1. **实测前提已反转**：`0e7d02b`（2026-10-09）已重锁，lock 内 gevent/greenlet 零命中——它描述的就是当前 0.10+ 依赖集；旧的"`uv sync` 会降级依赖、毁环境"警告全部出自 0.7.0 时代的失真描述。
2. **三种方式实测背书**：`uv lock` 补齐 mkdocstrings 后 `uv lock --check` 干净；再用隔离干净 venv（`uv venv --python 3.13` 后 `uv sync --extra dev --extra docs`）验证——pytest 9.1.1、ruff 0.16.10、mkdocs 全套装齐，全量 pytest 1017 passed / 1 skipped（skip 为可选原生扩展 `zoo_framework_native` 未装，良性）。证据目录 `.orca/tmp-bak/rh/clean-env`。
3. **删除是信息损失**：lock 能把贡献者的工具链钉死到可复现版本；在实测可用后删掉，等于放弃免费的可复现性。保留 lock + 把文档改回正常用法，是改动量与收益最优的一边。

注意 true-source 层级：`pyproject.toml` 仍是依赖唯一真源，`uv.lock` 是它的**锁定快照**（派生物），两者 `uv lock --check` 联动校验，不构成双真源。

### 2. bumpversion：删整段而非"修正数值"

`[tool.bumpversion]`（含 `[[tool.bumpversion.files]]` 两条文件替换规则）+ dev 依赖 `bump-my-version`，在发布流程（`scripts/next_version.py` + `sed`，release.yml:216-218）中**零引用**。修成 `0.10.6-beta` 只会把死工具洗成"看着能用的工具"，下次发版有人试它还会再次漂移。按"死配置删除"处置。

### 3. requirements-dev.txt：删除 + 指引归一

它是 `93afc18`（#93 删 requirements.txt）后幸存的第二真源：内容与 `[dev]` extra 分叉（多 hatchling / pytest-benchmark / bandit / structlog / types-PyYAML，部分不在 extra 里）。唯一引用点 development.md「方式二」。删文件 + 删该节 + conda 行 `python=3.11` → `3.13`（同族门槛过期，#114 已修过同文件 3.8）。

### 4. SECURITY.md（#115 第 4 条）：不动 dev 侧，记录移交

dev 分支的 SECURITY.md 已是无版本硬编码表述；`origin/main` 的仍是含 `0.5.3-beta` 的旧文。dev→main 合并即覆盖。本 change 只做事后 grep 复核动作记录，不新增文件改动。

## 风险与边界

- **release 流程零接触**：改动不碰 `scripts/next_version.py`、release.yml、`.env`、`zoo_framework/__init__.py`。
- **`[[tool.bumpversion.files]]` 若真有人跑 bump-my-version 会改 `.env` 与 `__init__.py`**——删除后该风险自然消失。
- uv 警告收敛后，CLAUDE.md 的「pip 备用路径」段同步改为中性说明，避免 CLAUDE.md 成为最后一个冒着旧警告的地方。
- 干净 venv 的 skip 不算失败：与 CI 口径一致（原生扩展是 optional build feature）。
