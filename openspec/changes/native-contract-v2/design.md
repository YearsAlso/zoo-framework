# design — native-contract-v2

> **本变更只交付设计与规格。** 实施 MUST 经维护者批准（裁决项见文末「Open Questions」），
> 本次不改 `zoo_framework/`、不改 `native/src`、不动 `CONTRACT_VERSION`。

## Context

- 现状（v1）：`zoo_framework/native/contract.py` 的 `CONTRACT_VERSION = 1`；扩展暴露四个入口
  `contract_version() / capabilities() / tasks() / execute(task, payload)`；`execute` 返回
  UTF-8 JSON 字节，适配器 `convert_output` 按 `output_format ∈ {"bytes","json"}` 解码。
- 实测依据：`native/DECISION.md` 读数边界④——125reg 上「Rust 侧 JSON 构建 + Python 侧
  `json.loads`」合计约 8µs（P3 13.3 − supp 5.1）；阶段 2 的转换/编排占比 0.66。
- 站内口径：`docs/ARCHITECTURE.md`「转换/编排占端到端 ~66%，是后续契约 v2 的优化候选」。
- 纪律约束（沿用既有设计，不重新论证）：内核 MUST NOT 依赖 PyO3/Tokio；执行体不回调 Python；
  `panic = "unwind"` 保持；不引入第二套调度/状态/簿记。

## Goals / Non-Goals

**Goals**
- 把「扩展直出纯 Python 对象」定为契约的一等输出形态，省掉「Rust 序列化 → Python 反序列化」。
- 明确主版本变更的兼容与拒绝策略，使「版本不匹配」永远是**可诊断的显式失败**。
- 把「输出形状违约」的归属固定在三族之内，不新增第四族。
- 给出一条**可判定的**性能验收口径，避免用「理论省下 8µs」冒充结论。

**Non-Goals**
- 不改输入侧（`payload` 仍是 bytes）；不做零拷贝视图；不实现跨主版本兼容；不承诺具体收益。

## Decisions

### D1 — 契约主版本变更的兼容策略：单一主版本 + 硬切换

**现状机制（v1，可直接引用为实施落点）**：适配器 `NativeAdapter.ensure_ready()` 幂等加载
扩展模块，随后 `_handshake()` 读 `contract_version()`；非整数或缺失 → `NativeInvalidInput`
（「未实现 contract_version()；不兼容」）；`version != CONTRACT_VERSION` → `NativeInvalidInput`
（「契约版本不匹配：扩展上报 {version}，框架支持 {CONTRACT_VERSION}」）。版本检查发生在
**任何任务执行之前**，因此不匹配的扩展不会被执行体碰到一次。

**CONTRACT_VERSION 递增规则**（与 `docs/native-tasks.md` 既有演进规则同源，本变更把它写成
可验证的 spec 条款）：

- 递增的唯一理由：**四个入口的形状或语义发生不兼容变更**（本次：`execute` 的返回形态）。
- MUST NOT 递增：新增任务、新增能力、新增一个 `output_format` 取值本身。
- 递增后 MUST NOT 提供「尽力兼容」：框架只支持**一个**主版本常量。

**拒绝面（两个方向都要）**：

| 场景 | 结果 | 错误内容 |
|---|---|---|
| v1 扩展 + v2 框架 | 执行前拒绝 | 上报 1，框架支持 2 |
| v2 扩展 + v1 框架 | 执行前拒绝 | 上报 2，框架支持 1 |

两个方向都靠同一条 `version != CONTRACT_VERSION` 判据，无需新增分支——这也是「单一常量」的
好处：只有一处真源，不存在两侧各自维护兼容表。

**备选与拒绝理由**：

- **A（拒绝）范围接受 `{1, 2}`，适配器同时支持两种输出形态**：代价是双版本转换面**永久存在**
  （适配器、校验器、模板、测试矩阵都要翻倍），而唯一在册的 v1 扩展是本仓自研样例，装机量≈自身；
  更重要的是它与仓库纪律正面冲突——「未实现的模式 MUST NOT 被静默执行成另一个模式」的精神是
  **宁可响亮失败，不猜**。
- **B（拒绝）用 `native:contractVersion` 配置挑选契约版本**：该键（`native_params.py`
  `NATIVE_CONTRACT_VERSION`，默认 0）目前在运行路径上**未被消费**（仅声明 + 参数解析测试）。
  把它变成「兼容开关」等于把「版本不匹配」从**错误**降级为**配置**，正是本框架反复拒绝的
  「静默降级」。→ 处置见 Open Questions Q4。
- **C（拒绝）新增第五入口 `execute_python()` 而保持 v1 不动**：见 D5。

**配对与依赖**：扩展包（`zoo-framework-native`）与框架是**锁定配对**——主包用
`native = ["zoo-framework-native>=0.1,<0.2"]` 声明范围（native-distribution D5：扩展版本与
契约版本是两条曲线）。v2 实施时 MUST 把该范围收紧到 `>=0.2,<0.3` 并提升扩展包 minor，否则
pip 会给用户装上一个**会被框架拒绝**的旧扩展——那是比不装更难诊断的状态。

### D2 — 输出从 bytes(JSON) 改为 Python 对象的**所有权与生命周期**

**边界与两个窗口**（这是本决策的实质）：现有形状是「`py.detach(执行体)` → 拿回 `Vec<u8>` →
交 Python 解码」。v2 保持同一个双窗口结构，只把第二个窗口的产物从**字节**换成**对象**：

| 窗口 | 持 GIL | 允许做的事 | 禁止做的事 |
|---|---|---|---|
| 执行窗口 | 否（`py.detach`） | 全部业务计算、I/O | 触碰任何 Python 对象 |
| 构造窗口 | 是 | **仅为**构造返回对象（分配 + 填值），有界 | 业务计算、I/O、长循环 |

构造窗口与今天 `to_json()` 之后的返回路径**同形**（今天也是在持 GIL 的边界把 `Vec<u8>` 包装
成 bytes 对象），所以「执行体不回调 Python」这条纪律**不被违反**：构造发生在执行体**之后**的
边界，不是执行**期间**的回调。

**所有权（MUST 逐条满足）**：

1. 返回对象是**新构造**的 Python 对象，引用计数从 0 → 1 交给调用方；不存在「借用 Rust 缓冲区」
   的形态（那是 `zero_copy`，本变更仍不承诺）。
2. **所有权一次性转移**：扩展在返回后 MUST NOT 继续持有或修改该对象；框架不会为「扩展稍后还想
   改」保留语义。
3. 对象由 Python 侧持有并进入 `WorkerResult.content`，可能被多个订阅者**共享引用**——因此
   框架与订阅者 MUST NOT 假定它可以被就地修改；需要可变结构的任务 MUST 每次返回新对象。
4. 生命周期不与扩展侧的 Rust 内存绑定：不存在「对象活着但底层缓冲区已释放」的状态（这正是
   零拷贝要单独设计持有者与释放时机的原因，见既有 spec 的「高频复用的输入退出后仍可读」）。

**对象图的纯度约束**：只允许 `None / bool / int / float / str / bytes / list / tuple /
dict(str 键)`。**禁止**出现：pyclass 实例（含 `NativeTaskContract` 这类框架对象）、`Py<T>` /
`Bound<T>` 句柄、迭代器/生成器、Rust 内存视图。理由有二：一是 spec 的核心承诺
「契约 MUST NOT 暴露原生绑定类型到内核」；二是等价性判据（Rust 输出 == 纯 Python 参考实现）
要求对象图可**逐值比较**，包装对象与惰性迭代器都会让它不可判定。

**失败归属**：执行窗口内 panic → 仍是 `NativePanic`（unwind 兜底，语义不变）；构造窗口内的
非受控异常（含分配失败）→ 经 PyO3 转成 Python 异常 → 适配器兜 `NativePanic`。

### D3 — `output_format` 的取值扩展与既有任务迁移

取值集合：`{"bytes", "json", "python"}`（v1 的两个取值**保留且语义不变**）。

| 取值 | 扩展返回 | 适配器行为 | 典型任务 |
|---|---|---|---|
| `"bytes"` | 不透明字节 | 原样返回 `bytes` | 二进制产物、加密块 |
| `"json"` | UTF-8 JSON 文本 | `json.loads` 解码（v1 语义不变） | 输出本来就是外部 JSON 文本的透传 |
| **`"python"`（新）** | 纯 Python 数据对象 | **不编解码**，只校验纯度与原样移交 | 结构化解析结果（样例：Modbus 帧解析） |

**命名决策**：用 `"python"` 而非 `"dict"`。`"dict"` 过窄——`list` 与标量同样是合法的纯数据对象图，
且「dict」与既有「json」在语义上极易混淆（一个是 Python 对象，一个是字节文本）。`"python"` 直接
表达「这一侧是 Python 对象」。

**字段形状不变**：`NativeTaskContract.output_format` 仍是 `str`，**不引入枚举类型**——契约是
**数据**，Rust 侧要构造同名值（native-distribution / add-native-task-execution D1 的既有理由）。
取值集合的真源在 `docs/native-tasks.md` 的四个入口表与 `native/validate_contract.py` 里机械核对。

**v1 取值在 v2 中是否继续合法？** 是。删除 `"json"` 会把破坏面扩大到不必要的第三方任务（例如
「输出就是一段外部 JSON 文本」的网关任务）。因此 v2 的**破坏性**并不来自取值集合的收缩，而来自
**版本常量递增导致所有 v1 扩展被拒** + `execute` 返回类型声明的改变——这两条就足够构成主版本跃迁。

**既有任务迁移**：

| 对象 | 现在 | 迁移后 | 理由 |
|---|---|---|---|
| 本仓样例 `modbus_rtu.parse_response` | `output_format="json"` | `"python"` | 参考实现 `parse_response` 本就返回 dict；两侧逐值等价判据不变，且省掉 8µs 往返 |
| 输出为结构化数据的第三方任务 | `"json"` | 建议 `"python"` | 同上；但属自愿 |
| 输出为外部 JSON 文本 / 不透明字节 | `"json"` / `"bytes"` | **不变** | 语义本就不同，v2 保留 |

**不存在混跑状态**：主版本不匹配即拒绝，所以不会出现「v2 框架 + 声明 v1 取值的扩展」这种
需要兼容表的状态。迁移 MUST NOT 依赖双版本并存（见 D1 备选 A 的拒绝理由）。

**实施落点**：`NativeAdapter.convert_output`（现有 `bytes`/`json` 分支保留，新增 `python` 分支：
纯度校验后原样返回；未知取值仍 `NativeInvalidInput`）+ `NativeAdapter.execute` 去掉
`bytes(output)` 的无条件强转。

### D4 — 三族错误语义是否受影响：不受影响，且新失败模式归入既有族

三族定义与映射路径**不变**：`NativeInvalidInput`（边界拒绝）/ `NativeTaskFailed`（受控业务
失败）/ `NativePanic`（unwind 兜底）；`NativeTaskContract.error_classes` 字段语义不变。

v2 只新增一种**失败模式**，其归属必须现在就钉死，否则实施时会各写各的：

| 新失败模式 | 归属 | 依据 |
|---|---|---|
| 扩展上报契约版本不匹配 | `NativeInvalidInput` | 握手期、执行前；v1 已是此归属 |
| `"python"` 输出不是纯数据对象图 | **`NativeInvalidInput`** | 与 v1「输出无法按 JSON 解码」**同族**——`contract.py` 的 `NativeInvalidInput` docstring 已明确把「输出无法按契约解码（执行后）」归入本族 |
| 执行窗口内 panic / 构造窗口内非受控异常 | `NativePanic` | unwind 兜底语义不变 |
| 业务结论（CRC 不符、功能码不支持等） | `NativeTaskFailed` | 不变 |

**MUST NOT 新增第四族**（例如把输出违约拆成 `NativeOutputContractViolation`）：三族是
`docs/native-tasks.md` 的公开承诺，`except` 子句与第三方 catch 面都按三族写；加一族会静默
改变所有既有捕获方的行为。输出违约是**受控的契约违例**，不是崩溃（→ 不是 Panic）、也不是
业务对数据的判断（→ 不是 TaskFailed），放 `NativeInvalidInput` 是唯一自洽的位置。

**错误质量要求**：违约错误 MUST 指名「哪个任务、期望什么、实际是什么类型」——这是唯一可诊断面。

### D5 — `execute(task, payload)` 签名的冲击

| | v1 | v2 |
|---|---|---|
| 入参 | `(task: str, payload: bytes)` | **不变** |
| 返回（声明） | `bytes`（约定 UTF-8 JSON） | `bytes \| object`，由该任务契约的 `output_format` 决定 |
| Python 适配器 | `return bytes(output)` 无条件强转；`convert_output` 按 `bytes`/`json` 解码 | 按 `output_format` 分派；`"python"` 只校验纯度、原样移交 |
| Rust 侧 | `fn execute(...) -> PyResult<Vec<u8>>`（`to_json()`） | 分派：`"bytes"`/`"json"` 分支同 v1；`"python"` 分支在返回到 Python 之前构造对象 |

**冲击面（实施清单，非本次）**：

1. `zoo_framework/native/adapter.py`：`execute()` 去掉 `bytes(...)`；`convert_output()` 增加
   `python` 分支与纯度校验。**校验顺序不变**（未就绪 → 未注册 → 输入超限 → 执行 → 输出转换）。
2. `zoo_framework/native/contract.py`：`CONTRACT_VERSION` 1 → 2（**本次不动**）。
3. `native/src/lib.rs` + `contract.rs`：返回类型分派；`"python"` 分支构造 `PyDict`/对象图。
4. `native/template/**`（第三方照抄的起点）与 `native/validate_contract.py`（机械校验器）
   MUST 同步改：模板的返回形状、校验器对返回类型的检查。
5. `docs/native-tasks.md` 的四个入口表与演进规则 MUST 更新「execute 返回值」一行。
6. 类型面：适配器返回值在 Python 侧是 `Any`/`object`。**MUST NOT 让 `Any` 泄漏到内核**——
   它是**边界值**，出适配器即被校验，进入 `WorkerResult.content` 后由订阅者自行解释。

**既有承诺 MUST NOT 被破坏**：结果仍只经单一结算点（`run_and_settle → settle`）投递；
`WorkerResult` 形状、run_id/session_id 盖章、超时熔断与停机语义全部不变。

**备选与拒绝理由**：

- **第五入口 `execute_python()`（拒绝）**：框架得先知道「该任务该调哪个入口」，于是要么扩展同时
  实现两个入口（契约面翻倍、校验器要判「两个是否都存在且语义一致」），要么在契约里加「用哪个入口」
  的字段（等于把 D3 的 `output_format` 换个地方再写一遍）。v2 的目标是**减少一层往返**，不是
  在入口层再分一次叉。
- **给 `execute` 传 `output_format` 入参（拒绝）**：把本属**契约**（静态声明）的信息挪到**调用**
  （动态），移除了「扩展声明什么、适配器就按什么处理」的可机械校验性，也让第三方任务无法自证。

### D6 — 性能验收口径（沿用四链路对照与 P50/P99 门槛）

**沿用（不重新发明）**：四链路对照 P1 纯 Python 参考 / P2 既有原生库形态 / P3 Rust 直调 /
P4 适配链；**同一次运行内**完成全部测量（读数纪律③：不跨运行拼接）；预热分离（300 次）、
事前固定迭代数、冻结样本帧组；**等价性前置检查**（Rust 输出与参考实现逐值一致）不通过即中止。
脚本形态沿用 `native/stage2_acceptance.py` 与 `native/envelope_remeasure.py`，落盘 `native/results/`。

**门槛（沿用的部分）**：P50 加速 ≥1.5x 且 P99 劣化 ≤5%（维护者已确认的 go/no-go 门槛）。

**增量判据（本次新增，草案）**：以「v2 的 P4」对「v1 的 P4」在同一运行内的差值判定：

| 档位 | 判据 | 备注 |
|---|---|---|
| 125reg（255B）大帧 | P50 改善达门槛值，且 P99 劣化 ≤5% | 上限量级 ≈ 读数边界④的 ~8µs |
| 3reg（11B）边界档 | **不得劣化** | v1 该档仅 1.57x，已贴门槛，无余量 |
| 7B / 9B 小帧 | 仍为 no-go | v2 MUST NOT 把 no-go 改判成 go |

**诚实性要求（重要）**：`~8µs` 是**上限量级**，不是预期净收益——省下的是 JSON 编解码，但
**构造 Python 对象本身也有成本**（PyDict 分配 + 逐项 `set_item`）。因此：

1. MUST NOT 用「8µs 减去零」外推净收益；必须实测 v2 与 v1 的 P4 差值。
2. **门槛的具体数值（例如 P50 改善 ≥ 10%）属维护者裁决项**（见 Open Questions Q3），
   本文只给判据形状与上限量级。
3. 未达门槛 → 如实记 no-go、保留 v1；rollback = 回溯契约常量与扩展构建（无数据迁移、
   无持久化状态），成本有界。

## Risks / Trade-offs

- [破坏性变更的使用者成本] → 单一主版本、错误双版本可诊断；扩展包与框架锁定配对（依赖范围收紧
  让 pip 报明确的不满足，而不是静默装旧扩展）。
- [收益可能显著小于 8µs] → 先测后定；把「对象构造成本」写进判据，禁止外推。
- [GIL 构造窗口成为新瓶颈] → 构造窗口 MUST 有界（只分配 + 填值）；若大输出的构造成本反超解码，
  记录为新的读数边界并回退到 `"json"`（v2 保留该取值正是为此）。
- [`Any`/`object` 泄漏] → 出适配器即校验；内核只见对象、不做形状假设。
- [三族边界被侵蚀] → 输出违约 MUST 归 `NativeInvalidInput`，新增第四族被明令禁止。

## Migration Plan

1. **维护者裁决**（实施前置）：D1 硬切换、D3 命名、D6 门槛数值与是否作为默认路径。
2. 契约常量 1 → 2；适配器分派 + 纯度校验；Rust 侧返回分派；本仓样例任务切 `"python"`。
3. 同步模板 / 校验器 / `docs/native-tasks.md` / 扩展包 minor 与 `native` 附加范围。
4. 同一次运行内的四链路对照 + 三族回归（含新增的「输出形状违约」用例）。
5. 达标 → 归档实现（并把 `native/DECISION.md` 的候选标记改为已实施）；未达 → 记 no-go、保留 v1。

## Open Questions

1. **Q1 主版本递增是否必要**：严格说「放宽返回类型」本身可向后兼容，因此存在「不动版本号、只加
   取值」的选项。本提案主张**递增**，理由是四个入口的对外承诺与 `docs/native-tasks.md` 的契约表
   都变了，且框架与扩展锁定配对——**需维护者裁决**是否采用硬切换。
2. **Q2 命名**：`"python"` vs `"dict"`（本文主张 `"python"`）。
3. **Q3 门槛数值**：125reg 的 P50 改善门槛取多少（上限量级 ~8µs）、是否把 `"python"` 作为样例/
   文档的默认推荐路径。
4. **Q4 `native:contractVersion` 配置键的处置**：它当前未被运行路径消费。三选一：保持为
   「声明式期望版本」（不一致即拒绝，错误带上期望值）／明确标注为未消费并删除／不启用。
5. **Q5 过渡窗口**：第三方扩展是否需要一个明确的弃用/迁移说明窗口（本提案主张硬切换 + 显著
   标注，不设双版本期）。
6. **Q6 输入侧**：是否把「扩展接收 Python 对象作为输入」也纳入后续变更（本变更明确不做）。
