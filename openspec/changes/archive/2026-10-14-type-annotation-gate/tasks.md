# tasks — type-annotation-gate

## 1. 规格（spec-first）

- [x] 1.1 `specs/ci-and-packaging/spec.md` 写入 ADDED Requirement：文档站构建 MUST 以
      严格模式作为门禁，且构建与部署分离（dev/PR 构建、main 部署）
- [x] 1.2 `specs/type-checking/spec.md` 写入 ADDED Requirement：进入 API 参考的公开签名
      MUST 带类型注解，并逐模块开启严格模式
- [x] 1.3 `openspec validate type-annotation-gate --strict` 通过

## 2. 实现

- [x] 2.1 补齐 40 处签名注解（12 个模块）：
      `core/params_path.py`、`core/container/container.py`、`core/waiter/base_waiter.py`、
      `core/waiter/dispatch_core.py`、`core/waiter/scheduler_model.py`、
      `event/event_channel.py`、`reactor/event_reactor_manager.py`、
      `reactor/waiter_result_reactor.py`、`statemachine/state_effect_scheduler.py`、
      `statemachine/state_machine_manager.py`、`workers/async_worker.py`、
      `workers/base_worker.py`
- [x] 2.2 `mkdocs.yml`：`strict: true`，更正末尾与实际不符的注释
- [x] 2.3 `.github/workflows/docs.yml`：`mkdocs build --strict`；触发补 `dev` 与 PR；
      `mkdocs.yml` 纳入触发路径；部署作业加 `if: github.ref == 'refs/heads/main'`
- [x] 2.4 `pyproject.toml`：为 `zoo_framework.core.params_path` 与
      `zoo_framework.statemachine.state_effect_scheduler` 开启 `disallow_untyped_defs`
- [x] 2.5 对 `StateNodeIndex` 缺方法的两处调用加逐行 `type: ignore[attr-defined]`
      与说明注释（不改行为）

## 3. 验证

- [x] 3.1 `mkdocs build --strict` 退出码 0：griffe 告警 **40 → 0**、链接告警 **1 → 0**
- [x] 3.2 `mypy zoo_framework`：Success，0 error（107 个源文件）
- [x] 3.3 `ruff check zoo_framework` 与 `ruff format --check zoo_framework` 通过
- [x] 3.4 导入烟测：`import zoo_framework` 及 worker/waiter/statemachine 路径正常
      （期间修掉一处循环导入：`WorkerResult` 改为从子模块导入）
- [x] 3.5 全量 `pytest` 已按"已知基线失败、与本改动无关"记录（归档时补记，2026-10-14）：
      改动前后的 dev 基线上该失败同样存在，即前后对照成立。注意该 heredoc 用例的**根因**
      已由另一次变更 `fix-release-notes-heredoc` 单独修掉（见其 3.4 的 tag 实测），
      两者是独立的失败来源，不作因果混淆
- [x] 3.6 CI 三平台 `docs --strict` 与新触发条件实测（归档时补记，2026-10-14）：
      以 `dev` 上最近一次推送（合并 PR #244，`v0.13.2-beta`）为证，`Quality Check` /
      `Tests` / `Build` / `CodeQL` 四个作业全部 `success`（`gh run list --branch dev --limit 12`），
      其中 `Tests` 覆盖三平台矩阵、`Quality Check` 覆盖 `docs --strict` 与新触发条件
