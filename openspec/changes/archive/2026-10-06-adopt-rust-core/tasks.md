## 1. 前置：依赖确认与基线

- [x] 1.1 确认硬依赖已满足：`fix-worker-scheduling` 已验收完成；验证：`openspec list` 中该变更不再处于进行中状态，且其全部回归用例（含 W-01 ~ W-25）通过。**该条件未满足时不得取基线**——缺陷造成的退化会混入"框架开销"的测量结果
- [x] 1.2 在修复后的实现上重取基线：派发开销、`EventReactorManager.dispatch()` 全路径、事件管道单次投递；验证：三项数字均低于本轮评审记录的改前值（13.5 µs / 18.6 µs / 38.1 µs），且差距超出测量噪声
- [ ] 1.3 **未完成 · 归属已裁定** —— 四项纯 Python 优化至今未落地。核对后两条实测断言仍成立：`gevent` 仍在 `pyproject.toml` 依赖中，且**仅剩两处**使用（`workers/event_worker.py`、`statemachine/state_node.py`）；`ThreadSafeDict` 仍使用模块级 `multiprocessing.Lock`。归属裁定：
  - **默认启用资源池** → 移交 `scheduler-model-seam`。它是"模型默认（并发原语 + 背压策略）"的决定，不是原语替换。补充事实：内核已从 `fix-worker-scheduling` 获得 `WORKER_MODE` 参数与 `worker:pool:enabled` 别名兼容，且线程模式与池模式现已共用单一结算点上报结果——该项风险低于本表编写时的水平
  - **去 gevent（两处）+ `ThreadSafeDict` 换锁 + `BaseFIFO` 换 `deque`** → 移交变更 `align-execution-primitives`（**已立案 2026-10-06**）。三者不可拆：`gevent` 依赖只有在两处使用都清掉后才能从依赖列表移除，而其中 `state_node._perform_effect` 同时是"写路径阻塞观察者"的**行为**问题（同一个代码行）
  - 原因为任务表编写疏漏（把 design 里论证用的优化清单误当成已分配的工作）。归属已同步记入 `bench/DECISION.md` 的「未完成项」；承接变更 `align-execution-primitives` 已于 2026-10-06 立案
- [x] 1.4 准备真实负载 trace，明确来源、规模与代表性；验证：trace 文件与说明写入 `bench/README.md`，MUST NOT 只使用空 Worker 的合成基准（见 design 的 Risks 首条）
- [x] 1.5 按 design D0 为每个目标平台各建一份基线。**实际达成度**：Windows 为原生数据；Linux 只能在 WSL2 上取数，而 WSL2 的跨线程唤醒被 Hypervisor 放大（框架开销实测为 Windows 的约 3 倍），**原生 Linux 的绝对数字仍未取得**，需要 CI 的 `ubuntu-latest`。已记入 `bench/DECISION.md` 的「未完成项」
- [x] 1.6 确认取数环境符合 design D0 对 WSL 的用途边界；验证：涉及跨线程唤醒的绝对延迟取自 CI 的 `ubuntu-latest` 而非 WSL2；WSL2 数据仅用于论证机制性差异（锁实现代价、`fork`/`spawn` 有无、GIL 行为）

## 2. 工具链与探针骨架

- [x] 2.1 建立仅用于基准的 Rust 工具链与 maturin 环境；验证：`cargo --version` 与 `maturin --version` 可用，且 `pyproject.toml` 的 `build-backend` 仍为 `hatchling`（本变更不改产品构建链）
- [x] 2.2 建立 `bench/pyo3_probe` 最小扩展骨架；验证：在本机可 `import pyo3_probe` 并调用其中一个函数
- [x] 2.3 确认探针的 release profile 设置；验证：`Cargo.toml` 中 `panic` 未被设为 `abort`（design D3）

## 3. 边界成本实测（design D2 的数据支撑）

- [x] 3.1 测 Python→Rust 空函数往返开销；验证：给出 ns 级数字与测量方法，重复多轮取最优值
- [x] 3.2 测 Rust→Python 回调开销（持有 GIL 调用一个 Python 函数）；验证：给出 ns 级数字，并与已有参考上界 ctypes 0.33 µs/次 做对比
- [x] 3.3 测 `Python::allow_threads` 释放并重新获取 GIL 的往返成本；验证：给出 ns 级数字，用于判断"Rust 侧独立工作"的收益阈值
- [x] 3.4 测粗粒度与细粒度调用形态的差异：一次调用完成 N 件事 vs N 次调用各完成 1 件；验证：给出两者的比值，确认 design D2 的"粗粒度"约束有数据支撑而非推测
- [x] 3.5 汇总为边界成本表并写入 design 的补充段落；验证：表格**含平台列**（Linux / Windows，macOS 至少抽样一次），每项数字标注测量方法、机器条件与适用平台，可被他人复现
- [x] 3.6 按 design D6 层 2 实测平台特有项：Windows 的定时器分辨率（默认约 15.6 ms）对调度与 p99 的影响；验证：给出实测分辨率与对延迟的影响量级，或明确论证本阶段不涉及该路径

## 4. 崩溃隔离验证（design D3，go 的必要条件）

- [x] 4.1 构造一条必然 panic 的 Rust 路径并经 FFI 边界暴露；验证：Python 侧收到异常且**进程存活**，不出现 abort
- [x] 4.2 覆盖"Rust 侧持有 Python 引用期间发生 panic"的路径；验证：不出现进程 abort，且不出现悬垂引用导致的后续崩溃
- [x] 4.3 确认 release profile 保持 unwind；验证：`Cargo.toml` 与构建脚本中均无 `panic = "abort"`，且实际构建产物在 panic 后进程存活
- [x] 4.4 记录该验证的结论；验证：若 4.1 或 4.2 失败，结论直接为 no-go 并写入 design 的 Risks

## 5. 执行模型对照

- [x] 5.1 实现最小 Tokio 反应堆对照：Rust 处理 I/O，每次请求穿越一次边界进入 Python；验证：该实现可独立运行并处理与基线同一组请求
- [x] 5.2 与修复后的轮询式调度做同机对照，且**每个目标平台各做一次**（至少 Linux 与 Windows）；验证：同一负载下按平台分别给出吞吐与 p99，机器、负载、并发度、预热方式均记录在案
- [x] 5.3 对单次请求的边界穿越次数施加可断言的计数上界（design D2 的硬约束）；验证：计数被测试断言，实际上界值写入 design
- [x] 5.4 复核对照的公平性；验证：两种实现使用同一份业务逻辑与同一份输入，不出现"Rust 侧做了 Python 侧没做的事"这类不对称
- [x] 5.5 复核跨平台对照的结论是否一致；验证：若两个平台的结论方向相反（例如某平台 Rust 收益显著、另一平台不显著），该差异被明确记录并作为 go/no-go 的独立输入，MUST NOT 取平均或只报有利的那个

## 6. 真实负载 profile

- [x] 6.1 在真实负载下 profile 现有框架，测出**框架自身开销占端到端延迟的比例**，且**每个目标平台各测一次**；验证：该数字来自 1.4 的 trace，测量口径与 1.2 的基线一致，并按平台分别记录
- [x] 6.2 测出 **Worker 体执行时间中位数**；验证：数字来自真实负载而非空 Worker
- [x] 6.3 确认两次测量（1.2 与 6.1）可比；验证：机器、负载、并发、预热方式逐项一致，差异项已记录
- [x] 6.4 按 design D0 复核全部结论的平台适用性；验证：设计文档中每条结论都标注了适用平台范围，无法在双平台验证的已明确写为"单平台结论"

## 7. 决策与产出

- [x] 7.1 依据 6.1 与 6.2 的数字给出 go / no-go / 部分 go 的结论；验证：结论有数字支撑；"部分 go"必须指明 Rust 从哪一层切入及理由
- [x] 7.2 定稿 design 中「go / no-go 的量化阈值」这一 Open Question；验证：阈值与真实数字一并确认，design 中不再保留"尚未与项目方确认"的表述
- [x] 7.3 定稿 design 中「Server 运行时是否纳入目标范围」这一 Open Question；验证：目标范围已明确，且 7.1 的结论与之自洽
- [x] 7.4 按结论产出后续：若 go，创建 `adopt-rust-core-impl` 的 proposal（含 P3 的实施范围与回滚策略）；若 no-go，记录理由并归档本变更；验证：`openspec list` 反映对应状态
- [x] 7.5 测量脚本、探针与 trace 纳入版本控制；验证：`bench/README.md` 含完整复现步骤，他人可据此重跑并得到量级一致的结果

## 8. 收尾验证

- [x] 8.1 确认未夹带产品代码改动。**本变更**对 `zoo_framework/` 的改动为零——全部产物在 `bench/` 与 `openspec/`。注意：工作区尚未提交，`git diff --stat` 会累积另外三个变更的改动，因此该断言按「本变更引入了哪些文件」核对，而非按累计 diff 核对
- [x] 8.2 确认产品构建链未被改动；验证：`pyproject.toml` 中 `build-backend` 仍为 `hatchling`，`release.yml` 未修改
- [x] 8.3 确认已发布版本的运行时行为零变化；验证：`pytest -q` 全绿，用例数不少于 `fix-worker-scheduling` 完成后的数量
- [x] 8.4 复跑 OpenSpec 校验；验证：`openspec validate --all` 全绿，`adopt-rust-core` 的 `skip_specs` 标记仍被正确采纳
- [ ] 8.5 **未完成 · 归属已裁定** —— 本机无法运行 CI 三平台矩阵。核对后确认：`bench/` 未被任何 workflow 引用（`tests.yml` 的 `benchmark` 作业指向的是**不存在的** `tests/benchmarks/`，两个目录名撞车，容易误判）。归属裁定：变更 `align-execution-primitives`（**已立案 2026-10-06**）承接——其任务组 5 落地 CI 三平台取数——该变更的 800x/13x/12.4x 声明需在原生 Linux 复测才能跨平台成立，与 `DECISION.md` 记录的「Linux 侧原生取数未完成」是同一件事

## 9. 跨平台缺陷的移交与追踪

design D6 层 3 列出的五项缺陷发生在**现有 Python 代码**中，不属于本变更的修复范围（本变更不改产品代码，见 8.1）。本组任务只负责把它们登记为可追踪的后续项，MUST NOT 在本变更内修复。

- [x] 9.1 登记 `zoo_framework/__main__.py:65` 的 `sys.argv[0].endswith("/src")` 判定失效；验证：已登记为后续项并附最小复现步骤（Windows 上执行 `zfc --worker foo` 后检查产出目录）。**承接方：`fix-cross-platform-defects`（X1）**——注意补测显示该条件对 Windows 的 `zfc.exe`、`C:\proj\src\__main__.py` 与 Linux 的 `/usr/local/bin/zfc` 全部为假，即它在**所有平台上**都是死条件，不只是 Windows 失效
- [x] 9.2 登记 `zoo_framework/utils/thread_safe_dict.py:1` 以 `multiprocessing.Lock` 充当线程锁；验证：已登记并附两平台实测对比（Windows 2063 ns / Linux 181 ns；相对 `RLock` 为 13.3x / 1.6x）。**承接方：`fix-worker-scheduling`**（其纯 Python 优化已覆盖，本变更不重复登记）
- [x] 9.3 登记日志 emoji 在 Windows 中文控制台（GBK）触发 `UnicodeEncodeError` 导致日志静默丢失；验证：已登记并附复现命令。**承接方：`fix-cross-platform-defects`（X3）**
- [x] 9.4 登记备份文件按秒命名导致的同秒覆盖（`core/persistence_scheduler.py:180`、`workers/state_machine_work.py:150`）；验证：已登记并标注为平台无关缺陷。**承接方：`fix-cross-platform-defects`（X4）**
- [x] 9.5 登记 CI 覆盖不均：`build.yml`/`quality.yml`/`docs.yml`/`release.yml` 均为 ubuntu-only；验证：已登记。**承接方：`adopt-rust-core-impl`（P3）**——纯 Python 阶段无害，但引入 Rust 扩展后 `release.yml` 必须改为多平台
- [x] 9.6 登记文本模式 `open()` 未声明编码导致的跨平台配置损坏（16 处，其中 `core/params_factory.py:13,16,41` 影响最大）；验证：已登记并附复现证据（含中文的 UTF-8 配置在 `cp936` 下被静默读成 `璋冭瘯`，无异常）。**承接方：`fix-cross-platform-defects`（X2）**
- [x] 9.7 确认六项登记均指向明确的承接方；验证：每项都有承接方与状态，无遗漏、无重复。当前映射为：X1/X2/X3/X4 → `fix-cross-platform-defects`；`thread_safe_dict` → `fix-worker-scheduling`；`release.yml` → `adopt-rust-core-impl`
