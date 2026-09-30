# 变更日志 / Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

本节以下的条目按 **Added / Changed / Deprecated / Removed / Fixed / Security** 分类，
只记录对使用者有影响的变化——内部重构若无行为影响，归入 Changed 并一句话说明。

---

## [Unreleased]

### Added

- 仓库标准化文档：重写 `README.md`（中英双语、能力清单、同类方案对比、社区与反馈渠道），
  新增 `CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`，以及 GitHub 的 issue 模板
  与 PR 模板。

- **按作用域解析的容器** `core/container/`：`ScopedContainer`（`register` / `resolve` /
  `exclusive` / `release` / `replace` / `reset`）、`Scope` + `ScopeKind`（进程 / 会话 /
  原型三种作用域）、必填的 `ThreadSafety` 线程安全声明，以及 `process_scoped` /
  `process_instance`（登记但**不替换类**，供框架自身的进程级管理器使用）。
- 注册项支持 `on_release` 销毁钩子：作用域释放时每个实例触发一次，不做引用计数。

### Changed

- 调度器（Waiter）的装配方式改为按**调度模型名**键控：`worker:mode` 选择调度模型
  （`thread` / `thread_pool`，留空时由 `worker:pool:enable` 推导），未实现的模式
  （`process` / `process_pool`）被显式拒绝。
- `worker:runPolicy` 的语义收窄为 `ThreadPoolModel` 的**背压策略**——`simple`（扩容）/
  `stable`（排队）/ `safe`（拒绝）——不再用于选择调度器子类。
- 模型无关的簿记逻辑（单一结算收口、超时观测与熔断、停机资源回收、运行期注册）下沉到
  `WorkerDispatchCore`，由 `BaseWaiter` 与调度模型组合使用。

### Removed

- `SimpleWaiter` / `StableWaiter` / `SafeWaiter` 三个子类。它们此前的唯一差异是"池尺寸
  不足时怎么办"，现已由 `ThreadPoolModel` 的背压策略参数承载。
- ⚠️ **破坏性变更：`@cage` 装饰器已删除** —— 不再从 `zoo_framework.core.aop` 或
  `zoo_framework.core` 导出，`core/aop/cage.py` 已移除。它此前把类替换成工厂函数，使
  `issubclass` / `isinstance` 双双失效（曾由此造成一次 P0），并且按**裸类名**做键（两个同名
  类会互相覆盖）。框架自身原有的 8 处使用点已改由容器的进程级注册承担，调用点零改动。
  自建单例请改用显式注册：

  ```python
  from zoo_framework.core.container import Scope, ScopeKind, ThreadSafety

  container.register(
      MyService,
      scope_kind=ScopeKind.PROCESS,
      thread_safety=ThreadSafety.INSTANCE_GUARANTEED,
  )
  service = container.resolve(MyService, Scope.process())
  ```

  `thread_safety` 与 `scope` 句柄均为**必填**，刻意不提供隐式默认值——隐式默认一个安全假设、
  或默认"不传即进程级"，都会静默破坏隔离。另注意「进程级作用域」**不等于**「单例」：容器
  另有会话级与原型级作用域。

### Fixed

- `@params` 的解析缓存由**裸类名**改为**模块 + 限定名**。此前两个定义在不同模块的同名参数类会
  命中同一条缓存——后定义者跳过解析、直接复用前者的配置值，且发生在导入期、无任何提示。

---

## 历史版本 / Historical releases

以下版本的说明由发布工作流在打标签时**自动生成**（内容是区间内的提交标题列表），
**未经人工整理**，仅供参考。本文件从下一个版本起改为人工维护。

| 版本 | 类型 | 发布日期 | 说明 |
|---|---|---|---|
| [v0.6.0](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.6.0) | 正式版 | 2026-02-19 | 发布工作流自动生成 |
| [v0.5.4-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.4-beta) | 预发布 | 2026-02-19 | 同上 |
| [v0.5.3-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.3-beta) | 预发布 | 2026-02-19 | 同上 |
| [v0.5.2-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.2-beta) | 预发布 | 2026-02-19 | 同上 |
| [v0.5.1-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.1-beta) | 预发布 | 2026-02-18 | 同上 |

> **版本号一致性提示。** 当前分支（`dev`）的 `pyproject.toml` 声明的是 `0.5.3-beta`，
> 而 GitHub 上最新的已发布版本是 `v0.6.0`；另有 `0.6.1-beta` 与 `0.7.0` 的版本号提交
> 位于尚未合并的分支上（`origin/fix/release`、`refactor/cli-package`）。
> 版本号同时存在于 `pyproject.toml`、`.env` 与 `zoo_framework/__init__.py` 三处，
> 修改时需一并更新。发布新版本前请先核对这三处与上方标签的对应关系。

---

## 版本号约定

| 触发方式 | 版本自增 | 稳定性 |
|---|---|---|
| 推送到 `dev`（PR 合并） | patch，带 `-beta` 后缀 | 预发布 |
| 推送到 `main` | minor，无后缀 | 正式版 |

发布由 `.github/workflows/release.yml` 完成，仅在 `zoo_framework/`、`pyproject.toml`、
`.env` 或该工作流本身发生变更时触发——纯文档或纯测试提交不会触发发版。
