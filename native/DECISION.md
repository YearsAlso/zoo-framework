# DECISION — add-native-task-execution / 阶段 0 与阶段 2 测量记录

> **本文档中的 Modbus 是样例负载，不是框架功能。** `modbus_rtu.parse_response` 是
> 阶段 0 为判定 go/no-go 选定的首个真实业务任务，随后随 `native/` 扩展一并发布。
> 它的作用有二：提供可复现的收益证据（本文件与 `native/results/`），以及充当两侧
> 语义等价的对照体（`native/reference/modbus_rtu.py`）。
> 框架侧 `zoo_framework/native/` 与具体任务无关——只按任务名分派、不认识任何业务
> 语义；生产部署 SHOULD 以自有任务替换之（移除样例须同步摘除 `native/src/lib.rs`
> 与 `contract.rs` 中的注册点，框架侧无需改动）。替换掉样例不影响本文件测量结论的
> 有效性——它是对「粗粒度原生任务」这一形态的判定，Modbus 只是承载该判定的样本。

## 结论（第二组测量：首个真实任务四链路对照）

**go，附工作包络：Modbus RTU 响应帧解析在 ≥3 寄存器（≥11 字节）帧上端到端收益
1.57x–9.63x，稳过维护者门槛（P50 ≥1.5x 且 P99 劣化 ≤5%）；2 寄存器（9 字节）及更小帧
收益 1.00x–1.29x，未过门槛——该段 MUST 留在 Python 侧，不路由原生。**

> 包络于 2026-10-12 由 issue #130 在同方法下补测小帧区间后，**由 ≥8 寄存器（≥21 字节）
> 下调到 ≥3 寄存器（≥11 字节）**。旧门槛来自对三个测量点的线性外推，本次实测证实外推
> 成立、而旧值偏保守。依据与决策轨迹见下文「包络重测」。

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

**工作包络（接入指导）**：帧 ≥3 寄存器（≥11 字节）路由原生；更小帧留在 Python
侧——P2 形态 1.10µs 已是同机最优，无需原生。该门槛于 2026-10-12 补测后由 ≥8 寄存器
下调，依据见「包络重测」。

附：`supp_rust_raw`（裸 `execute`，不含 JSON 解析）P50 = 0.40 / 0.70 / 5.10µs
（1reg / 8reg / 125reg），用于推算转换占比，见读数边界④。

### 4. 间接证据（此前 bench/DECISION.md 已留档，此处引用不重测）

- 跨界成本 28.9 ns（是旧 design 估算的 1/11）——单任务跨界税可忽略；收益稀释
  主因是线程调度与任务边界，而非 GIL 往返。

## 包络重测（issue #130，2026-10-12）

**动机**：用本文三个实测点线性外推得到的门槛是 **10.3 字节**，而当时写入接入指导的是
**≥21 字节**——10–21 字节区间可能是未被利用的收益区间。#130 要求补测 10 / 12 / 16 字节三点。

**一个必须先说的事实**：Modbus RTU 响应帧长恒为 **5 + 2N**（1 地址 + 1 功能码 + 1 字节数
+ 2N 数据 + 2 CRC，N 为寄存器数），即**恒为奇数**。10 / 12 / 16 构造不出结构自洽的合法帧
——它会被 `parse_response` 按「帧结构不一致」直接拒绝。故补测取最近的合法点：
**9B(2reg) / 11B(3reg) / 13B(4reg) / 15B(5reg)**，它们横跨了外推门槛。

**方法**：脚本 `native/envelope_remeasure.py`，与阶段 0 四链路对照同法（预热 300、连测
3000、同一次运行、等价性前置检查）。为遵守读数纪律③（不跨运行拼接），**原有三点
（7B / 21B / 255B）也在同一次运行内复测**，回归建立在单次运行的 7 个点上。

**数据**（P50，µs；判定对照维护者门槛）：

| 帧 | P1 纯 Python | P4 适配链路 | P4/P1 | P99 变化 | 判定 |
|---|---|---|---|---|---|
| 1reg（7B） | 3.30 | 3.30 | **1.00x** | +22.2% | **no-go** |
| 2reg（9B） | 4.40 | 3.40 | **1.29x** | −13.0% | **no-go** |
| 3reg（11B） | 5.50 | 3.50 | **1.57x** | −23.3% | go |
| 4reg（13B） | 6.70 | 3.50 | **1.91x** | −45.7% | go |
| 5reg（15B） | 7.90 | 3.60 | **2.19x** | −52.5% | go |
| 8reg（21B） | 11.00 | 3.90 | **2.82x** | −54.4% | go |
| 125reg（255B） | 142.50 | 14.80 | **9.63x** | −87.0% | go |

**回归**（本次运行 7 个点，F = 帧字节数）：

```
P1 = -0.643 + 0.56133·F    (R² = 0.999998)
P4 =  2.945 + 0.046479·F   (R² = 0.999919)
```

- 盈亏平衡（S = 1.00）：**F ≈ 6.97 字节**——与旧实测「7 字节 1.03x」吻合
- 维护者门槛（S ≥ 1.50）：**F ≈ 10.29 字节**

**结论**：#130 的外推**得到证实**——门槛确在 ~10.3 字节而不是 21 字节；最近的合法帧
11 字节（3 寄存器）实测 **1.57x**，且 P99 反而改善 23.3%。
**工作包络由 ≥8 寄存器（≥21 字节）下调为 ≥3 寄存器（≥11 字节）。**

决策轨迹如实保留在此、不覆盖旧数字：旧包络是**偏保守**而非错误——它建立在当时仅有三个
测量点的外推上，外推方向正确、幅度保守。

**未改动**：契约与适配器侧没有硬编码 21 字节的上限常量（`zoo_framework/native/` 内无命中），
故本次只改接入指导。

**未复测**：本机为 Windows 原生数据；Linux / macOS 的包络仍待 CI 原生构建后才算完整
（与「阶段 2 验收」的 tasks 5.3 是同一未完成项）。

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
| Linux | CI 原生构建已接入（`.github/workflows/native.yml`），数值待首次运行回填 | — |
| macOS | CI 原生构建已接入（同上），数值待首次运行回填 | — |

2026-10-12 之前 CI（GitHub Actions）无 maturin/cargo，真扩展用例在 CI 中显式 skip；该缺口
由 issue #129 / 变更 `native-distribution` 补上：`native.yml` 现在在三平台跑 `cargo test`、
构建 abi3 wheel、安装后执行原生 pytest 路径。故 Linux/macOS 的数字**待该工作流首次运行后
回填**，不再依赖「本机无验证路径」这一历史状态。WSL2 hypervisor 失真问题不适用
（本机为 Windows 原生测量）。

## 发行（issue #129，2026-10-12；变更 `native-distribution`）

在本次之前，go 结论**只存在于测量报告里**：`native/` 无任何 CI、无 wheel、PyPI 404。
本次把它变成可安装、可验证的交付物：

| 项 | 变更前 | 变更后 |
|---|---|---|
| CI 覆盖 | 无（8 个 workflow 全是 Python 侧） | `.github/workflows/native.yml`：三平台 `cargo test` + 构建 + 原生 pytest |
| abi3 | 未启用 | `abi3-py311`——一份 wheel 覆盖 3.11+（本机产物名含 `cp311-abi3`） |
| 扩展下界 | `requires-python >=3.13` | `>=3.11`（与 abi3 覆盖范围一致，否则收益被自己挡住） |
| 发布流水线 | 无 | `.github/workflows/native-release.yml`：manylinux + macOS + Windows，OIDC，TestPyPI 演练，版本已发布时幂等跳过 |
| 安装入口 | 无 | `pip install zoo-framework[native]`（形态 B：独立发行物 + 一条发现路径） |

**发行形态决策**（design D1）：选 B（可选附加）——对用户只多一个方括号、对分发只多一条
构建矩阵，同时保住「不装即纯 Python」。C（默认捆绑）会毁掉零依赖卖点；A（只有独立包名）
则让用户看不出它与框架的关系。

**未验证项（如实说明）**：`native-release.yml` 的发布链路**无法在本变更内验证**——真实
证据只在第一个 tag 或一次 TestPyPI 演练之后才存在；在那之前不得声称发布成功。

## pyo3 0.23 → 0.29 升级（issue #205，2026-10-12）

**动因**：Dependabot 的 3 条 open 告警**全部**命中 `native/Cargo.lock` 的 pyo3 0.23.5
（high：`PyList`/`PyTuple` 迭代器 `nth`/`nth_back` 越界读，0.29.0 修；medium：
`PyCFunction::new_closure` 缺 `Sync` bound，0.29.0 修；low：`PyString::from_object`
缓冲区溢出，0.24.1 修）。#93 曾把 Scorecard 的 Vulnerabilities 归因于 `uv.lock`，实测
不成立——Python 侧重锁后依赖版本零变化，真正的落点在这里。

**迁移点只有两处**（编译器逐条指出）：

| 0.23 | 0.29 | 位置 |
|---|---|---|
| `py.allow_threads(..)` | `py.detach(..)`（0.25 起改名） | `src/lib.rs` 的 `execute` |
| `Bound::downcast_into::<T>()` | `Bound::cast_into::<T>()` | `src/contract.rs` 的异常类解析 |

升级后与 `bench/pyo3_probe` **重新对齐**到同一版本带（探针独立升到 0.29 时本 crate 还停在
0.23，旧注释"同带"因此曾是错的）。

**边界行为逐条重测**（升级的义务写在「读数边界」里：升级 MUST 重测）：

1. **GIL 释放** —— `native/stage2_acceptance.py` 的 12 线程饱和形状：
   **8.43x**（升级前 7.49x）。多核伸缩只有在执行期间真的离开解释器时才可能出现，
   故这是 GIL 释放仍然成立、且更好的直接证据。
2. **panic 映射** —— **如实记为缺口**：`native/` 自身没有「跨 FFI 边界的 panic →
   PanicException」的直接测试。现状证据是两条间接的：
   (a) `tests/test_native_task_execution.py` 覆盖**适配器侧**映射（注入非三族异常 →
   `NativePanic`）；(b) pyo3 的边界转换是**版本带属性**，已由同版本带（0.29）的
   `bench/pyo3_probe` 三条 panic 路径验证（`panics()` / `catches_panic()` /
   `panics_holding_python_ref(f)`，见 docs/benchmark.md）。
   要把它变成直接证据，需要给扩展加一条自检入口或把探针的 panic 用例纳入 native 的 CI；
   本次**未做**，不声称已直接验证。
3. **既有测试全绿** —— `cargo test` 11 passed；安装升级后的 abi3 wheel 后
   `pytest tests/test_native_extension.py tests/test_native_task_execution.py` 44 passed。

**性能未退化**（四形状对照，升级前 → 升级后）：

| 形状 | 0.23 | 0.29 |
|---|---|---|
| single（125reg，K=1） | 9.87x | **9.78x** |
| batch_small（1reg，K=8） | 1.07x | **1.09x** |
| batch_large（125reg，K=64） | 10.22x | **10.34x** |
| saturate（125reg，12 线程） | 7.49x | **8.43x** |

**锁文件**：`native/Cargo.lock` 的 pyo3 已为 **0.29.3**；GitHub 重扫后 3 条
Dependabot 告警应随之关闭。

## 对 tasks 的指向

- [x] 1.1 首个真实任务 = Modbus RTU 响应帧解析（维护者 2026-10-09 选定，zoo-code-agent 已被维护者排除）
- [x] 1.2 事件管道候选链路剖析（native 下沉收益低——executor.submit 记账 31.9µs 主导，改由 `add-event-push-model` + `optimize-event-dispatch-batching` 承接，均已实施合入）
- [x] 1.3 四链路对照（本文件第三节 + `native/results/stage0_phase2_four_paths.json`）
- [x] 1.4 门槛确认（P50 ≥1.5x / P99 劣化 ≤5%）+ go 结论（附工作包络）
- [x] 3.1–3.4 Rust 扩展与首个任务（`native/` crate：`cargo test` 11 绿；pytest 加载路径/握手/等价性 9 绿，扩展缺席时显式 skip）
- [x] 4.x 注册接入（NativeTaskWorker 经 Master.register_worker / register_instance+add_worker 两路径派发已验证；超时熔断与停机三 Scenario 回归 + 断言注入验收，见 tasks 4.1–4.4）
- [x] 5.x 阶段 2 验收（四形状对照测量 + 晚到结果回归见「阶段 2 验收」附录；Windows 已测，Linux/macOS 待 CI 原生构建，`native/results/stage2_acceptance.json`）
- 12 并发获得最大核利用率形状 → 原生任务的池大小默认带 8–12 线程（注册接入时与 `worker:pool:size` 对齐）
