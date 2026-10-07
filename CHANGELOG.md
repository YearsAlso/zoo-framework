# 变更日志 / Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

本节以下的条目按 **Added / Changed / Deprecated / Removed / Fixed / Security** 分类，
只记录对使用者有影响的变化——内部重构若无行为影响，归入 Changed 并一句话说明。

---

## [Unreleased]

### Added

- 事件/持久化管道节拍可配（变更 `configurable-run-delay` / #73）：`event:delay`、
  `stateMachine:delay` 配置入口取代 `EventWorker` / `StateMachineWorker` 硬编码
  `delay_time=5`；默认值保持 5，行为向后兼容。此前每次事件派发都绑定秒级节拍且
  无法调节（时间敏感场景如 agent 工具循环的单步延迟被钉死在秒级）。

### Fixed

- 状态机读盘恢复不再为空操作（变更 `fix-state-restore` / #72）：`ThreadSafeDict` 非
  `dict` 子类，旧守卫对框架自家落盘文件恒假——状态从未恢复、`have_loaded()` 却声称
  已加载并挡死重试（含备份恢复路径）。现按真实类型分派：ThreadSafeDict 原样恢复、
  普通 dict 包装、未知类型 `TypeError` 拒绝；恢复语义裁定为整表替换。消费者
  zoo-code-agent 的"重启续跑"就此解除阻塞。

### Removed

- 死配置键 `event:sleep` 移除（#73）：随 gevent 消费循环删除后零消费，用户填写
  它没有任何效果——配置表"看起来可调"而实际不可调的误导终结。
- **运行依赖移除 `gevent`**（BREAKING，变更 `align-execution-primitives` / #31）：事件投递
  与状态 effect 改用 `concurrent.futures` 线程执行器；`greenlet` / `zope-event` /
  `zope-interface` 随之出依赖树（#34 由此解决），安装不再触发源码构建。
  直接依赖"框架顺带装上 gevent"的使用者需自行声明。
- `core/aop/validation.py` 整模块删除（`@validation` / `validation_params` /
  `params_validate_map`；零使用、零规格，#49）；`worker_registry.register_worker` 装饰器
  删除（死分支且与 `Master.register_worker` 构成第二注册真源）。

### Changed

- 容器外三个【已知欠债】进程级共享收编进框架容器（变更 `absorb-debt-carriers` /
  #50 交付 1，方案 A）：`EventReactorManager.reactor_map` 与
  `EventChannelRegister._channel_map` 降为进程级实例属性（类级读取经元类代理转发，
  既有写法兼容），`get_worker_registry()` 改由容器解析——`framework_container().reset()`
  即彻底复位，conftest 三处手工复位清单退役。`WorkerRegistry` 同步补齐实例内 RLock，
  `INSTANCE_GUARANTEED` 声明自此如实。无公共 API 变化；直接构造私有注册表的用法不变。
- `thread_pool` 调度模型的容器换为「固定工作线程 + `queue.Queue`」（变更
  `replace-pool-dispatch-queue` / #47 P2）：去除 Future 记账（本机提交侧记账
  4.07 µs → 0.61 µs）；背压三策略、单一结算收口、六项模型契约逐项不变，
  无 API 变化。停机"取消排队"语义等价：丢弃未开始任务、不中断已开始任务。
- 内部重构（无行为影响，变更 `declare-debt-carriers` / #50 切片一）：新增进程级共享
  载体登记表 `core/process_state.CARRIERS`，测试复位由它生成；扫描测试拦截未登记的
  新载体。顺带删除零读写的死类属性 `StateEffectScheduler._response_list`。
- AOP 的两条导入顺序约束从静默改为出声（变更 `aop-determinism` / #51）：
  参数类在"从未读到配置"的世代解析过、而 `Master` 随后读到配置 ⇒ 构造期点名报错；
  `Master` 消费注册表后再 `@configure` 注册 ⇒ 照常登记但告警"只有下一个 Master 会消费"。
  新增 `aop` 能力规格固化 `@configure`/`@logger`/`@stopwatch` 的注册时机、调用约定与失败模式。
  （BREAKING，窄：仅"先导入参数模块、后构造 Master"的错误时序从静默默认值转为报错；
  无配置的全默认运行与正常同目录用法不受影响。）
- 调度内核的策略解析（周期/相位/超时的"自报→覆盖→默认"三段）改为按 Worker 缓存
  （#47 P1）：解析语义逐项不变，falsy 配置值（`0`/`False`/`""`）仍是有效结果；
  调度列表替换、同名重注册、停机复位时自动失效。
- `ThreadSafeDict` 的互斥锁改为**每实例一把 `threading.RLock`**（原模块级单把
  `multiprocessing.Lock` 把全进程串行化）；锁不入 pickle，状态机持久化行为不变。
- `BaseFIFO` / `DelayFIFO` 存储换 `collections.deque`（出队 O(1)）；API 与空队返回
  `None` 的语义不变。
- 事件投递与状态 effect 的 join 超时项、回调异常从静默消失改为记入日志（可观测性
  增强；写路径同步等待 ≤5s 语义保留）。

### Deprecated

- `@worker` / `worker_register` 退出 `zoo_framework.core` 与 `core.aop` 的公共导出面（#49）；
  模块路径 `zoo_framework.core.aop.worker` 保留一个 minor 周期供迁移，使用时发
  `DeprecationWarning`。注册 Worker 的唯一接通路径是 `Master.register_worker(name, cls)`；
  下个 minor 连同 `workers.WorkerRegister` 一并删除。

---

## [0.8.0] - 2026-10-04

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
| [v0.8.0](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.8.0) | 正式版 | 2026-10-04 | 见上方 `[0.8.0]` 段（人工整理）。**含破坏性变更**：`@cage` 删除、`worker:mode` 键控、`worker:runPolicy` 语义收窄 |
| [v0.7.1-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.7.1-beta) | 预发布 | 2026-09-30 | 发布工作流自动生成 |
| [v0.6.0](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.6.0) | 正式版 | 2026-02-19 | 发布工作流自动生成 |
| [v0.5.4-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.4-beta) | 预发布 | 2026-02-19 | 同上 |
| [v0.5.3-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.3-beta) | 预发布 | 2026-02-19 | 同上 |
| [v0.5.2-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.2-beta) | 预发布 | 2026-02-19 | 同上 |
| [v0.5.1-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.1-beta) | 预发布 | 2026-02-18 | 同上 |

> **版本号一致性提示。** `dev` 与 `main` 的三处版本声明（`pyproject.toml` / `.env` /
> `zoo_framework/__init__.py`）现均为 **`0.8.0`**，与最新标签 **`v0.8.0`**（2026-10-04）一致。
>
> ⚠️ **两条分支的版本线是各自独立的**：工作流的版本算术只读「**收到推送的那个分支自己的
> 声明值**」—— `main` 走 minor、`dev` 走 patch。因此**每次从 `main` 发版后，`main` 的新版本线
> 不会自动回到 `dev`**；不回流的话，`dev` 的下一次 bump 会算出一个**比刚发布的版本还低**的号。
>
> 本仓库已实际踩过一次：`0.8.0` 发布后，`dev` 基于残留的 `0.7.1-beta` 开出了升到
> `0.7.2-beta` 的 PR（已关闭 —— 合它会把一个**旧线**的 beta 发到 `0.8.0` 之后）。
> **发版后请把 `main` 的版本声明同步回 `dev`。**
>
> 三处必须一起改：版本号同时存在于 `pyproject.toml`、`.env` 与
> `zoo_framework/__init__.py`，少改一处就会出现「发出的包对自己的版本撒谎」。
> `[tool.bumpversion].current_version` 也同步维护以求自洽，但它不在发布路径上 ——
> 发版版本号由 `.github/workflows/release.yml` 自己算。
>
> 另有一个陷阱：**只改版本声明的推送会被判成「打 tag」而非「开 bump PR」**。若那个 tag
> 已存在，该步骤会就地报错中止（刻意不改写既有 tag）。所以版本对齐宜与一个**非版本文件**
> 的改动同批推送。

---

## 版本号约定

| 触发方式 | 版本自增 | 稳定性 |
|---|---|---|
| 推送到 `dev`（PR 合并） | patch，带 `-beta` 后缀 | 预发布 |
| 推送到 `main` | minor，无后缀 | 正式版 |

发布由 `.github/workflows/release.yml` 完成，仅在 `zoo_framework/`、`pyproject.toml`、
`.env` 或该工作流本身发生变更时触发——纯文档或纯测试提交不会触发发版。
