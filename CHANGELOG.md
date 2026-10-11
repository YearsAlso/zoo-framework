# 变更日志 / Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的组织方式，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

本节以下的条目按 **Added / Changed / Deprecated / Removed / Fixed / Security** 分类，
只记录对使用者有影响的变化——内部重构若无行为影响，归入 Changed 并一句话说明。

---

## [Unreleased]

### Security

- 供应链加固状态收口（#121）：新增 `docs/SECURITY_MODEL.md`（使用者视角的安全说明，含
  "未做的事"）与 `docs/security-supply-chain.md`（#89–#95 的实际生效状态，逐条带证据）。
  依赖漏洞状态复核结论：**锁定集合扫描 0 命中**，未改动任何依赖版本；第二份依赖清单
  （`requirements*.txt`）已删除，真源唯一。
- 补齐最后一处 action 未钉 SHA（#91）：`release.yml` 的 `actions/checkout` 由 `@v4` 钉到
  commit SHA；`SECURITY.md` 的支持版本表去掉会漂移的版本举例（#97 的收尾）。

## [0.10.6-beta] - 2026-10-10

### Changed

- 使用者文档入口指向独立文档站
  [yearsalso.github.io/zoo-framework-doc](https://yearsalso.github.io/zoo-framework-doc/)
  （中英双语 VitePress，含安装/教程/概念/API），仓库内 `docs/README.md` 保留为维护者
  与贡献者文档并显式分工。无代码行为变化。

## [0.10.5-beta] - 2026-10-10

### Added

- 文档信息架构重建（变更 `docs-ia-rebuild`）：`docs/` 按「使用者/贡献者」分流——
  教程（01-05 五篇，每步有期望输出）、按"我要做 X"组织的指南、mkdocstrings
  自动生成的 API 参考、迁移指南（`docs/MIGRATION.md`，逐项含报错原文）、
  版本政策（`docs/VERSION_POLICY.md`）、品牌与视觉规范。

## [0.10.4-beta] - 2026-10-10

### Changed

- 运行时报错消息与公共 API docstring **英文化**（变更 `api-docstring-english`）：
  所有运行时 `raise` 消息与 `zoo_framework/` 公共 docstring 统一为英文——设计目标是
  AI 生成代码的全球可用性（报错可被通用检索）。中文文档与注释保持中文。行为不变；
  若此前依赖中文报错文本做 grep 处理，需改为匹配英文消息或按异常类型捕获。

## [0.10.3-beta] - 2026-10-10

### Added

- **原生任务执行（可选 Rust 扩展）**（变更 `add-native-task-execution` / #110）：
  新增独立构建的可选扩展包（PyO3），经握手与能力清单接入；配置键族 `native:*`
  （`native:enabled` 默认 false）、任务名-适配器登记表、
  未安装扩展时不影响任何现有功能，**显式请求原生能力时明确报错**（不静默回退）。
  来源：`bench/` 的 go/no-go 决策（no-go 判定）后选定的窄口方案。

## [0.10.2-beta] - 2026-10-09

### Added

- **自适应调度（epsilon-greedy bandit）**（变更 `add-adaptive-scheduling`）：新增
  `DualArmWorker`（`zoo_framework.workers`）— 以在线自学的路由决策在「原生/Python」
  双臂间选择执行体；配置键族 `adaptive:*`，**`adaptive:enabled` 默认 false**（关闭时
  纯 Python 臂执行，零开销）。bandit 统计可持久化（`adaptive:statsPath`）。
- **事件管道推模型**（变更 `event-push-model`）：`EventChannel.push_event` 生产者
  入队即 notify，消费者无事件**挂起等待**（零空转轮询）；拉模型语义保留。
- **批量投递**（变更 `event-dispatch-batching`）：同一 reactor 的多个事件一次
  executor 提交摊薄记账开销。

## [0.10.1-beta] - 2026-10-09

### Security

- 供应链与权限收紧（#90 #91 #94）：工作流 token 权限收敛到最小集；全部第三方
  actions 钉住 commit SHA（防 tag 改写）；release 产物附 `.sig` / `.pem` 签名。

### Removed

- 删除失真的 `requirements.txt`（#93）：内容与 `pyproject.toml` 长期 drifted（第二
  依赖真源误导）。依赖唯一真源 = `pyproject.toml`。

## [0.10.0] - 2026-10-08

正式版聚合：本版本区间无独立变更条目——**内容与 [0.9.2-beta] 相同**（dev 线
`0.9.2-beta -> 0.10.0` 版本号晋升，见 CHANGELOG 底部的版本号约定）。

## [0.9.2-beta] - 2026-10-08

### Changed

- 发布自动化版本线跨分支连续（变更 `fix-release-version-continuity` / #82，维护者
  不可见行为）：dev 算版本以 main 声明为下限抬升（逻辑入 `scripts/next_version.py`，
  可单测）；main bump 合并后自动向 dev 开 back-merge PR；back-merge 的声明回声不再
  误触打 tag。背景：main=0.9.0 后 dev 沿旧线连发过 0.8.3b0/0.8.4b0（人工回并修过
  现象，本变更修机制）。

## [0.9.1-beta] - 2026-10-07

### Added

- 事件/持久化管道节拍可配（变更 `configurable-run-delay` / #73）：`event:delay`、
  `stateMachine:delay` 配置入口取代 `EventWorker` / `StateMachineWorker` 硬编码
  `delay_time=5`；默认值保持 5，行为向后兼容。此前事件派发绑定秒级节拍且无法调节
  （时间敏感场景如 agent 工具循环的单步延迟被钉死在秒级）。

### Fixed

- **`zfc --worker` 在项目外从静默成功改为明确失败**（BREAKING，变更
  `fix-zfc-worker-project-root` / #131）：先前在任意目录执行会返回 0 并留下一个
  无入口导入的游离 `workers/` 目录——文件永远不会被加载或调度，调用方却无从得知。
  现在从当前目录向父目录查找最近含 `src/main.py` 的脚手架项目；找不到时在写入前
  以非 0 退出码失败并给出下一步，不产生任何文件或目录。此前依赖在项目外直接生成
  `./workers/` 的调用需先运行 `zfc --create <name>` 或切换到项目目录。
- 状态机读盘恢复不再为空操作（变更 `fix-state-restore` / #72）：`ThreadSafeDict` 非
  `dict` 子类，旧守卫对框架自家落盘文件恒假——状态从未恢复、`have_loaded()` 却声称
  已加载并挡死重试（含备份恢复路径）。现按真实类型分派：ThreadSafeDict 原样恢复、
  普通 dict 包装、未知类型 `TypeError` 拒绝；恢复语义裁定为整表替换。消费者
  zoo-code-agent 的"重启续跑"就此解除阻塞。

## [0.9.0] - 2026-10-06

**首个 minor 正式版**。0.8.1-beta ~ 0.8.4-beta 是本版发布线的先行 beta（同日交叉
发布），完整内容以本段为准。

### Added

- 进程级共享载体登记表与扫描拦截（变更 `declare-debt-carriers` / #50 切片一）；
  随后收编三处进程级欠债进框架容器（`absorb-debt-carriers` / #50 交付 1，方案 A）：
  `EventReactorManager.reactor_map` 与 `EventChannelRegister._channel_map` 降为进程级
  实例属性（类级读取经元类代理转发，既有写法兼容），`get_worker_registry()` 改由
  容器解析——`framework_container().reset()` 即彻底复位。
- 调度内核策略解析按 Worker 缓存（#47 P1）：三段语义不变，falsy 配置值仍有效。
- 调度模型接缝（`scheduler-model-seam` / #47）：`ThreadPerTaskModel` /
  `ThreadPoolModel` 抽象，时间语义与运行标识补全。

### Changed

- **执行原语对齐**（BREAKING 的 Removed 见下；变更 `align-execution-primitives` /
  #31）：事件投递与状态 effect 改用 `concurrent.futures` 线程执行器。
- `ThreadSafeDict` 互斥锁改为每实例一把 `threading.RLock`（原模块级
  `multiprocessing.Lock` 把全进程串行化）；锁不入 pickle。
- `BaseFIFO` / `DelayFIFO` 存储换 `collections.deque`（出队 O(1)）；API 不变。
- join 超时项与回调异常从静默消失改为记入日志。

### Deprecated

- `@worker` / `worker_register` 退出公共导出面（#49）：注册 Worker 的唯一接通路径是
  `Master.register_worker(name, cls)`（此前 legacy 表从未被派发链读取——见
  docs/MIGRATION.md「`@worker(count=N)` 装饰器」）。

### Removed

- **运行依赖移除 `gevent`**（BREAKING；#34 由此解决，安装不再触发源码构建）：
  直接依赖"框架顺带装上 gevent"的使用者需自行声明。迁移见
  docs/MIGRATION.md「gevent」节。
- `core/aop/validation.py` 整模块删除（`@validation` 零使用零规格，#49）；
  `worker_registry.register_worker` 装饰器删除。迁移见 docs/MIGRATION.md。
- AOP 时序错误从静默改为出声（`aop-determinism` / #51，窄破坏性）：仅"先导入参数
  模块、后构造 Master"的错误时序转为构造期报错；正常用法不受影响。

## [0.8.4-beta] - 2026-10-07

进程级欠债收编进框架容器交付（#50 方案 A）——完整条目见 [0.9.0] 段的收编条与
`get_worker_registry()` 语义。

## [0.8.3-beta] - 2026-10-07

`thread_pool` 调度模型容器换「固定工作线程 + `queue.Queue`」（#47 P2，提交侧记账
4.07 µs → 0.61 µs；背压三策略与停机语义逐项不变）——完整条目见 [0.9.0]/[0.8.0]
段对应 Changed 行。

## [0.8.2-beta] - 2026-10-06

0.9.0 发布线 beta：AOP 语义确定性（#51）、调度策略缓存、`@worker` 弃用、执行原语
对齐（去 gevent / ThreadSafeDict 按实例锁 / FIFO 换 deque）——完整条目见 [0.9.0] 段。

## [0.8.1-beta] - 2026-10-05

发布链路修复：tag 推送改用 PAT——否则「打 tag → 发布」会静默断链（维护者侧；
讽刺地，正因为这个断链本 beta 之后才多走了 3 个版本才到 0.9.0）。

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

以下版本**未做人工整理条目回填**：说明由发布工作流在打标签时自动生成（区间内提交
标题列表）；仓库历史中考据基础不足以编写可信条目，**宁可留空并标注，不编造**
（issue #117）。0.8.1-beta 起的版本已逐版回填（见上方）。

| 版本 | 类型 | 发布日期 | 说明 |
|---|---|---|---|
| [v0.8.0](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.8.0) | 正式版 | 2026-10-04 | 见上方 `[0.8.0]` 段（人工整理）。**含破坏性变更**：`@cage` 删除、`worker:mode` 键控、`worker:runPolicy` 语义收窄 |
| [v0.7.1-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.7.1-beta) | 预发布 | 2026-09-30 | **未回填**（考据基础不足，保留自动生成的提交列表） |
| [v0.6.0](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.6.0) | 正式版 | 2026-02-19 | **未回填**（同上） |
| [v0.5.4-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.4-beta) | 预发布 | 2026-02-19 | **未回填**（同上） |
| [v0.5.3-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.3-beta) | 预发布 | 2026-02-19 | **未回填**（同上） |
| [v0.5.2-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.2-beta) | 预发布 | 2026-02-19 | **未回填**（同上） |
| [v0.5.1-beta](https://github.com/YearsAlso/zoo-framework/releases/tag/v0.5.1-beta) | 预发布 | 2026-02-18 | **未回填**（同上） |

> 0.8.1-beta 起的版本已回填为逐版条目（见上方对应段；交叉发布的 beta 用交叉引用指向
> 承载完整内容的正式版段，issue #117）。

> **版本号一致性提示。** `dev` 与 `main` 的四处版本声明（`pyproject.toml` / `.env` /
> `zoo_framework/__init__.py` / `CITATION.cff`）均为 **`0.10.6-beta`**，与最新标签
> **`v0.10.6-beta`**（2026-10-10）一致。
>
> ⚠️ **两条分支的版本线是各自独立的**：工作流的版本算术只读「**收到推送的那个分支自己的
> 声明值**」—— `main` 走 minor、`dev` 走 patch。因此**每次从 `main` 发版后，`main` 的新版本线
> 不会自动回到 `dev`**；不回流的话，`dev` 的下一次 bump 会算出一个**比刚发布的版本还低**的号。
>
> 本仓库已实际踩过一次：`0.8.0` 发布后，`dev` 基于残留的 `0.7.1-beta` 开出了升到
> `0.7.2-beta` 的 PR（已关闭 —— 合它会把一个**旧线**的 beta 发到 `0.8.0` 之后）。
> **发版后请把 `main` 的版本声明同步回 `dev`。**
>
> 四处必须一起改：版本号同时存在于 `pyproject.toml`、`.env`、
> `zoo_framework/__init__.py` 与 `CITATION.cff`，少改一处就会出现「发出的包对自己的版本撒谎」。
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
