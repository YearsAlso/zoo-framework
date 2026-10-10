# repo-hygiene 任务清单

## 1. 版本声明真源唯一（issue #115 第 1 条）

- [ ] 1.1 删除 `pyproject.toml` 的 `[tool.bumpversion]` 整段（含
      `[[tool.bumpversion.files]]` 子条目）与 `[dependency-groups]` / dev extras 里
      的 `bump-my-version`（验证：grep `current_version`、`bump` 零命中）
- [ ] 1.2 确认三处版本声明一致（pyproject `^version`、`.env` `^VERSION=`、
      `__init__.py __version__` 均为 0.10.6-beta；release 流程不改）（验证：grep）

## 2. uv.lock 与文档承诺一致（issue #115 第 2 条）

- [ ] 2.1 提交已完成的 `uv lock` 重锁（补 mkdocstrings）；`uv lock --check` 干净
      （验证：uv lock --check 0 退出）
- [ ] 2.2 三处 uv 警告收敛：README.md:409,415 / README.zh.md:379,385 /
      CONTRIBUTING.md en:38,44-46、zh:315,321-323 改为一句正常用法说明
      （验证：grep " devastat\|毁环境\|stale" 警告字样零命中）
- [ ] 2.3 CLAUDE.md 的「uv 备用路径」说明同步为中性描述（验证：grep pip fallback 段）

## 3. 依赖真源唯一（issue #115 第 3 条）

- [ ] 3.1 删除 `requirements-dev.txt`（验证：文件不存在）
- [ ] 3.2 development.md 删「方式二」节（约 L74-81）；`conda create -n zoo python=3.11`
      → `3.13`（验证：grep requirements-dev、3.11 零命中）

## 4. SECURITY.md main 合并复核（issue #115 第 4 条）

- [ ] 4.1 在 tasks 留移交记录：dev→main 合入后 grep `origin/main:SECURITY.md`
      确认无 `0.5.3-beta` 硬编码（验证：记录在案，不需要本分支改动）

## 5. 回归与验证

- [ ] 5.1 门禁：`ruff check` / `mypy`（改动文件范围内）；全量 pytest 全绿
      （验证：0 error / passed ≥ 当前基线）
- [ ] 5.2 `openspec validate repo-hygiene --strict` 通过（验证：0 警告）
- [ ] 5.3 提交（`Closes #115`）+ md5 核对（验证：无意外文件变化）
