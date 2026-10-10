# repo-hygiene 任务清单

## 1. 版本声明真源唯一（issue #115 第 1 条）

- [x] 1.1 删除 `pyproject.toml` 的 `[tool.bumpversion]` 整段（含
      `[[tool.bumpversion.files]]` 子条目）与 dev extras 里的 `bump-my-version`
      （验证：tomllib 解析确认 tool.bumpversion 不存在、dev 无 bump 项；release.yml
      的 "bump" 命中均为注释里的 "bump PR" 流程词，非 bumpversion）
- [x] 1.2 确认三处版本声明一致（pyproject `^version`、`.env` `^VERSION=`、
      `__init__.py __version__` 均为 0.10.6-beta；release 流程不改）（验证：grep 三处逐字一致）

## 2. uv.lock 与文档承诺一致（issue #115 第 2 条）

- [x] 2.1 提交 `uv.lock` 重锁：先补 mkdocstrings、再随 bump-my-version 删除一并
      re-lock（`uv lock` 幂等收敛，79 包）；`uv lock --check` 干净；lock 内
      bump/gevent/greenlet 零命中
      （验证：uv lock --check 通过；grep 计数 0）
- [x] 2.2 三处 uv 警告收敛：README.md / README.zh.md 贡献代码节、
      CONTRIBUTING.md 双语安装节改为一句"两种包管理器皆可用，解析同一套依赖"
      （验证：grep destroy/毁环境/stale-warn 字样零命中）
- [x] 2.3 CLAUDE.md 三处同步（Setup 命令注释、Note 段 `uv run --no-sync`、
      版本第三段 bumpversion 提及）（验证：grep 无残留）

## 3. 依赖真源唯一（issue #115 第 3 条）

- [x] 3.1 删除 `requirements-dev.txt`（验证：文件不存在；全库引用仅剩 openspec
      变更工件的描述性文本）
- [x] 3.2 development.md 删「方式二」节并注明 pyproject 是依赖唯一真源；
      `conda create -n zoo python=3.11` → `3.13`（验证：grep 两项零命中）

## 4. SECURITY.md main 合并复核（issue #115 第 4 条）

- [x] 4.1 **移交记录**：dev 分支 SECURITY.md 已是无版本硬编码的安全策略；
      `origin/main` 仍为含 `0.5.3-beta`（L12/L90）的旧文。待本分支经 dev→main
      流程合入后，复核动作 = `git show origin/main:SECURITY.md | grep 0.5.3`，
      预期零命中；未合入前 main 不动。（验证：移交记录在案，本分支零改动）

## 5. 回归与验证

- [x] 5.1 门禁：ruff check 全过；mypy 107 文件 0 error；全量 pytest
      **1029 passed**（验证：输出留痕）
- [x] 5.2 `openspec validate repo-hygiene --strict` 通过（验证：0 警告）
- [ ] 5.3 提交（`Closes #115`）+ md5 核对（验证：差异仅限预期文件）
