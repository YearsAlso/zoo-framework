# DECISION — add-native-task-execution / 阶段 0 与阶段 2 测量记录

## 结论（第二组测量：首个真实任务四链路对照）

**go，附工作包络：Modbus RTU 响应帧解析在 ≥8 寄存器（≥21 字节）帧上端到端收益
2.83x–9.71x，稳过维护者门槛（P50 ≥1.5x 且 P99 劣化 ≤5%）；1 寄存器小帧（7 字节）
收益 1.03x，未过门槛——该段 MUST 留在 Python 侧，不路由原生。**

这是部署形态（P4：经 `NativeAdapter` 全链路）对纯 Python 参考实现（P1）的
同机同运行对照，数据见「数据」第三节；逐轮明细已落盘
`native/results/stage0_phase2_four_paths.json`。

## 任务选定（tasks 1.1 / 1.4，维护者确认 2026-10-09）

- **首个真实任务：Modbus RTU 响应帧解析**（`modbus_rtu.parse_response`）。
  选定理由：ROADMAP 首位目标场景（IoT/嵌入式，设备管理线）的第一个真实负载；
  帧解析 + CRC16 是纯字节操作、无 GIL 内回调，符合「粗粒度原生任务」约束；
  边缘网关高频轮询是真实热点形态。
- **首版范围**：FC 0x03/0x04 正常响应帧 + 0x83/0x84 异常响应帧（异常码进输出，
  语义交调用方解释）+ CRC16-MODBUS（0xA001 反射，线上小端）。错误分类：
  长度 <4 / >256 → `NativeInvalidInput`（执行前拒绝）；CRC 不符 / 功能码不支持 /
  帧结构不一致 → `NativeTaskFailed`（受控业务失败——线上字节损坏是业务现实）。
- **go/no-go 门槛（维护者确认）**：端到端 P50 加速 ≥1.5x 且 P99 劣化 ≤5%，
  低于门槛即回退 no-go 结论。

## 第一组测量（受控形态）的结论

**NativeTaskWorker 的核心收益机制在本机成立：原生执行期间释放 GIL → CPU 任务
真多核伸缩。** 单任务加速比与多核伸缩率均已实测，不再是纸面推演。

## 测量环境

| 项 | 值 |
|---|---|
| 机器 | AMD Ryzen 9 5900X（12C/24T），Windows 11 Pro for Workstations |
| Python | 3.13（`.venv`，CPython 3.13.14） |
| Rust | rustc 1.98.1 / cargo 1.98.1 |
| 探针（第一组） | `bench/pyo3_probe`（PyO3 0.23 + tokio，cdylib，`panic="unwind"`） |
| 扩展（第二组） | `native/`（PyO3 0.23.5，cdylib，`panic="unwind"`，release profile 经 maturin 安装） |
| 测量脚本 | 第一组 `bench/stage0_phase1_scaling.py`（受控形态：整数迭代累加）；第二组 `bench/stage0_phase2_four_paths.py` |
| 读数纪律 | 预热分离（第一组 3 轮 / 第二组 300 次）；全套来自同一次运行；第二组等价性前置检查通过后才测 |

## 数据

### 1. 单任务加速比（第一组，n=200_000，受控形态）

| | 纯 Python | Rust 探针（`coarse_grained`，期间 `allow_threads`） |
|---|---|---|
| 中位 | 20.41 ms | 0.131 ms |
| min/max | 19.95 / 20.72 | 0.131 / 0.158 |
| **加速比 N** | | **≈ 155x** |

> 同形态手写循环的对照；真实业务任务的 N 视算法与输入而定（见「读数边界①」）。

### 2. 多线程伸缩（第一组，GIL 释放语义的证据）

完成同等总工作量（每线程连做固定任务数）下，W 个 Python 线程并发池中：

| 并发 W | 纯 Python 有效伸缩 | Rust 有效伸缩 |
|---|---|---|
| 2 | 0.44x（反伸缩，GIL 串行） | 1.67x |
| 4 | 0.21x | 3.93x |
| 12 | 0.11x | **5.87x** |
| 24 | 0.11x | 6.55x（趋饱和） |

- 纯 Python 的 CPU 任务在 `ThreadPoolModel` 下**零多核收益**（GIL 串行化，吞吐恒 ≈ 单线程，多线程反而被锁开销拖慢）——与 bench/DECISION.md 已知结论一致。
- Rust 原生任务**真实吃核**：12 并发拿到 5.87x（单线程封顶之下的 49% 核利用率），24 并发 6.55x 后趋平（Windows 调度与内存带宽主导）。
- 单任务较小时（0.13ms），任务级加速从 155x 稀释为 4–7x——**跨界与调度开销在小任务上占比升高**，证明 design 里「粗粒度 / 批处理」约束的必要性。

### 3. 四链路对照（第二组，Modbus RTU 响应帧解析，部署稳态）

P1 纯 Python 参考实现（位移 CRC + 手工切片，`native/reference/modbus_rtu.py`）/
P2 现有原生库形态（C 原语 `int.from_bytes` + 查表 CRC 循环，pymodbus 类典型形状）/
P3 Rust 直调（`zoo_framework_native.execute` + `json.loads`，交付等价产物）/
P4 Zoo+Rust 适配链路（`NativeAdapter.execute` + `convert_output` + 逐次契约查询——
部署形态）。n=3000/组合，预热 300，同一次运行：

| 帧 | P1 | P2 | P3 | P4 | **P4/P1 加速（P50）** | 判定 |
|---|---|---|---|---|---|---|
| 1reg（7B） | 3.40µs | 1.10µs | 1.90µs | 3.30µs | **1.03x** | **no-go** |
| 8reg（21B） | 11.30µs | 2.90µs | 2.50µs | 4.00µs | **2.83x** | go |
| 125reg（255B） | 145.60µs | 32.80µs | 13.30µs | 15.00µs | **9.71x** | go |

P99 全部改善（1reg −20.9% / 8reg −57.1% / 125reg −89.2%）——「P99 劣化 ≤5%」
门槛在所有尺寸上满足；1reg 的 no-go 纯粹由 P50 收益不足触发。

**工作包络（接入指导）**：帧 ≥8 寄存器（≥21 字节）路由原生；更小帧留在 Python
侧——P2 形态 1.10µs 已是同机最优，无需原生。

附：`supp_rust_raw`（裸 `execute`，不含 JSON 解析）P50 = 0.40 / 0.70 / 5.10µs
（1reg / 8reg / 125reg），用于推算转换占比，见读数边界④。

### 4. 间接证据（此前 bench/DECISION.md 已留档，此处引用不重测）

- 跨界成本 28.9 ns（是旧 design 估算的 1/11）——单任务跨界税可忽略；收益稀释
  主因是线程调度与任务边界，而非 GIL 往返。

## 读数边界（防止误读）

1. **155x 是本形态对照，不是任何业务任务的承诺**。155x 的来源是「手写 Python 循环 vs 优化后的 Rust 循环」的理想形态；真实任务若被 C 库顶住（json/regex/hash），N 掉到 1.5–3x；若含大量回调 Python 的步骤，回到 no-go 路线。Modbus 任务的实测净收益（9.71x @ 255B）等于把这条边界走了一遍。
2. **第二组的 P2 不是"现成原生库"的严格义**——stdlib 没有 Modbus CRC 的 C 实现，P2 代表 pymodbus 类既有实现的典型形状（C 原语 + Python CRC 循环），作为对照基线如实标注。
3. **适配链有 ~2.9µs 固定地板**（P4 − supp_rust_raw @ 1reg ≈ 2.9µs：契约查询、上限检查、`bytes()` 复制、`json.loads`）。这决定了小帧永远不划算——粗粒度约束从 design 推演升级为实测结论。
4. **输出转换占比可观**：125reg 上 JSON 构建（Rust 侧）+ 解码/`json.loads`（Python 侧）合计约 8µs（P3 13.3 − supp 5.1）。契约 v2 若改为扩展直出 Python dict 可再省一截——**仅记录为候选，未实施**（契约版本变更属新决策）。
5. 本机为 **Windows 原生**数据，无 WSL2 失真问题；跨平台状态见「阶段 2 验收」附录（Linux/macOS 待 CI 原生构建，tasks 5.3）。
6. **release profile 经产物量级核实**：supp_rust_raw @ 255B = 5.1µs；debug 形态会慢 10–30x，不可能到这个数。

## 阶段 2 验收（tasks 5.1–5.3，2026-10-10）

测量脚本 `native/stage2_acceptance.py`，落盘 `native/results/stage2_acceptance.json`。
纪律与阶段 0 相同：**同一次运行内完成全部测量；冻结帧组 + 事前固定迭代数**（非
「循环到达标」）；等价性前置检查（链路与参考实现逐值一致）不通过即中止。对照基线
为 P1 纯 Python 参考实现，被测对象为部署形态（P4：`NativeAdapter` 全链路）。

### 5.1 部署形态四形状对照（125reg 大帧为主，1reg 小帧作边界形状）

| 形状 | 帧 | 适配链路 P50 | 参考 P50 | 加速（P50） | 吞吐（帧/s） |
|---|---|---|---|---|---|
| single（K=1） | 125reg(255B) | 14.7µs | 145.1µs | **9.87x** | 65,710 |
| batch_small（K=8） | 1reg(7B) | 24.3µs/op | 25.9µs/op | **1.07x** | 315,232 |
| batch_large（K=64） | 125reg(255B) | 938.8µs/op | 9,597.1µs/op | **10.22x** | 66,203 |
| saturate（12 线程，K=1） | 125reg(255B) | —（墙钟吞吐口径） | — | **7.49x** | 48,543 |

- P99：single 29.1 vs 243.2（−88%）、batch_large 1,468.4 vs 11,328.9（−87%）
  ——工作包络内（≥8 寄存器）P99 全改善；batch_small（1reg）P99 劣化 +8.4%
  （46.4 vs 42.8），但该形状本就在工作包络外（no-go、留 Python 侧），与阶段 0
  判定一致，不构成门槛违约。
- **转换/编排占比 0.66**（single：适配链路 14.7µs − 裸 `ext.execute` 5.0µs ≈
  9.7µs 为转换+编排成本，占端到端 66%）——与阶段 0 读数边界④一致（契约查询、
  上限检查、`bytes()` 复制、`json.loads`）。契约 v2「扩展直出 dict」仍是候选，
  未实施。
- 与阶段 0 结论交叉核对：大帧端到端 9.87x–10.22x（阶段 0：9.71x）、小帧 1.07x
  （阶段 0：1.03x）、12 线程实伸缩 7.49x（阶段 0 受控形态：5.87x）——形状一致，
  结论无需修正。

### 5.2 行为场景覆盖

正常/失败/hooks（`TestNativeTaskWorker`）、四类显式拒绝（`TestAdapterHandshake`）、
超时熔断不声称终止 / 停机后不再接收新任务 / 幂等有界停机（`TestNativeStopSemantics`）
之外，本阶段补齐 **超时后晚到结果** 用例
`test_late_result_after_timeout_settles_once_without_residue`：熔断后任务才完成时，
结果恰好一次投递、`inflight` 清零无残留。断言有效性经注入验收（违规 1/3/4 变红
还原；违规 2 单层被纵深防御兜住），记录见 tasks 4.3。

### 5.3 平台对照

| 平台 | 状态 | 数据 |
|---|---|---|
| Windows 11 Pro for Workstations（10.0.26200，Ryzen 9 5900X 12C/24T，CPython 3.13.14） | 已测 | 本附录 + `stage2_acceptance.json` |
| Linux | 待 CI 原生构建补齐 | — |
| macOS | 待 CI 原生构建补齐 | — |

CI（GitHub Actions）当前无 maturin/cargo，真扩展用例在 CI 中显式 skip，故
Linux/macOS 数字待原生构建流水线落地后补测；WSL2 hypervisor 失真问题不适用
（本机为 Windows 原生测量）。

## 对 tasks 的指向

- [x] 1.1 首个真实任务 = Modbus RTU 响应帧解析（维护者 2026-10-09 选定，zoo-code-agent 已被维护者排除）
- [x] 1.2 事件管道候选链路剖析（native 下沉收益低——executor.submit 记账 31.9µs 主导，改由 `add-event-push-model` + `optimize-event-dispatch-batching` 承接，均已实施合入）
- [x] 1.3 四链路对照（本文件第三节 + `native/results/stage0_phase2_four_paths.json`）
- [x] 1.4 门槛确认（P50 ≥1.5x / P99 劣化 ≤5%）+ go 结论（附工作包络）
- [x] 3.1–3.4 Rust 扩展与首个任务（`native/` crate：`cargo test` 11 绿；pytest 加载路径/握手/等价性 9 绿，扩展缺席时显式 skip）
- [x] 4.x 注册接入（NativeTaskWorker 经 Master.register_worker / register_instance+add_worker 两路径派发已验证；超时熔断与停机三 Scenario 回归 + 断言注入验收，见 tasks 4.1–4.4）
- [x] 5.x 阶段 2 验收（四形状对照测量 + 晚到结果回归见「阶段 2 验收」附录；Windows 已测，Linux/macOS 待 CI 原生构建，`native/results/stage2_acceptance.json`）
- 12 并发获得最大核利用率形状 → 原生任务的池大小默认带 8–12 线程（注册接入时与 `worker:pool:size` 对齐）
