# proposal — add-native-task-execution

## Why

issue #88 的方向已定：让 Rust 执行**真实业务任务**（算法与数据转换体内不经过解释器），Python 保留入口、编排与生命周期。这与历史 no-go（`bench/DECISION.md`，测的是「Rust 派发 → 取 GIL → 跑 Python callable」，上限 1.67x）不是同一个问题——那是 Rust 编排 Python 执行体；本变更是热点执行体本身改为原生 Rust 实现，能否在语义等价的真实负载下取得值得承担构建与维护成本的端到端收益，**尚未测量**。

因此本变更采用「可选原生扩展 + 框架原生任务 Worker」的形状：框架不内置 Rust 依赖，原生扩展独立构建、按需安装；未安装时现有功能完全可用，显式请求原生能力时明确报错（不静默回退）。走可测量的 go/no-go（阶段 0），而不是一步到位引入常驻 Tokio 运行时或进程外 sidecar。

## What Changes

- 新增**语言无关执行契约**：描述任务选择、输入/输出、错误分类与能力查询；内核（契约接口与 Worker 形态）MUST NOT 直接依赖 PyO3 / Tokio / 具体业务任务。
- 新增 `NativeTaskWorker`：继承既有 Worker 生命周期（`BaseWorker.run()` → `_execute()` → hooks → `WorkerResult`），在 `_execute()` 内委托执行契约；结果只走既有单一结算点（`run_and_settle → settle`），MUST NOT 双重投递。
- 新增**原生适配器**：加载 Rust 扩展模块、校验契约版本与能力清单、转换输入/输出、把 Rust panic 与受控错误映射为 Python 异常。
- 新增可选 Rust 扩展包：`.pyd`/`.so`，含 `contract_version()`、能力清单与首个经阶段 0 选定的真实业务任务（沿用旧(py)探针的 `Python::detach` 名称——**固定新版 PyO3 后按该版本 API 实施，不复制旧探针**）。
- 任务在执行期间**释放 GIL / 脱离解释器**（ detach 语义），长任务执行时 Python 控制线程可推进。
- 首版复用既有 `ThreadPoolModel`：一个池线程同步执行一个原生 CPU 任务；MUST NOT 首版引入 Tokio 运行时或 Rust 侧第二层线程池。
- 配置以独立键族承载（`native:*`），全部可缺省且缺省为关闭；运行期原生 Worker 注册经 `WorkerRegistry.register_*` + `core.add_worker`。
- 不改变：既有 Worker 形态与调度语义、事件协议、pickle 格式、`ParamsPath` 三段解析、打包主路径（superset hatchling 純 Python 路径不变）。

**明确不做（首版）**：零拷贝缓冲区承诺、原生内部并行、常驻异步执行器（Tokio）、sidecar 进程隔离、取消=终止的承诺、`delay_time` 改造、唤醒机制改造、free-threaded 兼容声明式支持。

## Capabilities

### New Capabilities

- `native-task-execution`: 语言无关任务执行契约的形状与语义；NativeTaskWorker 的生命周期与单一结算；适配器的版本/能力校验与输入输出转换；缺失扩展的显式失败；GIL 释放语义与停机后资源边界。

### Modified Capabilities

- *(无)* —— 既有 `worker-lifecycle` / `worker-scheduling` / `scheduler-model` / `run-identity` 的 REQUIREMENTS 不变：原生 Worker 复用既有合约与结算收口；delta 不扩写这些能力。

## Impact

- **代码**: 新增 `zoo_framework/native/`（契约、worker、适配器，约 3-5 文件）；`params/` 新增 `native_params.py`（独立键族 `native:*`，含 `ParamsPath` 三段解析与 aliases 语义）；首个真实任务的 Rust 扩展以独立子目录（物理位置待定：树内独立目录 or 独立仓库；不与 `bench/pyo3_probe` 冒充混同）。约 8–15 文件、500–1500 行（首版不含选定后的真实负载迁移代码）。
- **API**: 无既有 API 变化。新增公共面：`NativeTaskWorker`、执行契约接口、适配器入口、`native_params` 键族。既有公共 API 与 `__init__` 导出面不变。
- **依赖**: `pyproject.toml` 主依赖**不变**——Rust/PyO3/maturin 只进扩展包自身的构建配置；遵循「不引入新第三方依赖」需用户确认的约定（**扩展包是独立构建物，非 `pyproject.toml` 升级**）。
- **构建/发布**: 扩展二进制独立构建产物，不进主 sdist；wheel 分阶段(阶段 3)另行评估。
- **CI**: 首版不强制原生门禁；原生扩展测试仅当本机具备 Rust 工具链时启用（skipif 机制）。
- **风险落点**: 转换成本（把输入/输出编解码留在契约边界）；同进程崩溃边界（`catch_unwind` 不能保证恢复 abort/段错误——只能在任务边界兜底 unwind panic）；构建矩阵漂移（版本固定进扩展包自身配置，非框架主配置）。

## 阶段 0 前提（不进入本 spec 的实现）

在写 `design.md` 之前，先产出一份**选定首个真实任务**的备忘录，证明以下三项：

1. 真实消费者调用链中存在可迁移热点（不是为证明 Rust 快而另造任务）；
2. 任务体占端到端耗时足够比例（转换/复制/编排其余部分不可支配整体收益，见 issue 的 Amdahl 示例：可迁移段 80% 且加速 10x，理论整体仅 3.57x）；
3. 维护成本与端到端收益的 go/no-go 门槛已被维护者确认。

阶段 0 未满足时，本变更**不进入实现**（design 与 tasks 标注该前置闸门）。
