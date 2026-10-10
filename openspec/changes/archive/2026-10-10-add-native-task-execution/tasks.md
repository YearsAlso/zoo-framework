# tasks — add-native-task-execution

> 前置闸门（design D7）：阶段 0 未通过（未选定真实任务 / 未确认 go/no-go）时，第 3 组起的实现任务**不执行**；变更以「阶段 0 未通过」结论收尾，不归档为已实现。
> **2026-10-09 闸门状态：已通过**（真实任务选定 + go 结论，见 `native/DECISION.md`），第 3 组起任务放行。

## 1. 阶段 0：选真实任务并建立可证伪基线

- [x] 1.1 确认首个真实消费者任务候选（zoo-code-agent 工具循环或设备协议解析），记录业务等价判据与候选理由；产出维护者确认
  - **2026-10-09 重估结论**：维护者排除 zoo-code-agent（仅框架本身）；候选「事件管道排空循环」经链路剖析（1.2）证实 native 下沉收益低（单事件成本被 executor.submit 记账 31.9µs 主导，可下沉段仅 1–2µs）。事件管道优化改由独立 change 承接：`add-event-push-model` + `optimize-event-dispatch-batching`（均已规划完成）
  - **2026-10-09 任务选定（闸门通过）**：首个真实任务 = **Modbus RTU 响应帧解析**（`modbus_rtu.parse_response`）——设备管理线（ROADMAP 首位场景）的第一个真实负载；帧解析 + CRC16 为纯字节操作、无 GIL 内回调，符合「粗粒度原生任务」约束。范围：FC 0x03/0x04 正常响应 + 0x83/0x84 异常帧（异常码进输出）+ CRC16-MODBUS（0xA001 反射、线上小端）；业务等价判据 = 与独立参考实现逐值一致（含三族错误分类）
- [x] 1.2 剖析完整链路（输入到达 → 调度等待 → 排队 → 输入转换 → 任务执行 → 输出转换 → 结果接收），同一次运行内分段采集，遵守 bench/ 三条读数硬约束；验证：剖析记录含转换/编排占比与离散度
  - **2026-10-09 剖析记录**：候选「事件管道排空循环」逐段成本拆解见对话留档（出队 ~50ns / 过期+查找 ~µs / **executor.submit 31.9µs=唯一大头且不可跨语言下沉** / 等待有界）；结论——候选任务的可下沉段占比过低，native 化收益预期从「高」降为「低」。受控形态测量（任务体加速/伸缩）已另录 `native/DECISION.md` 第一组数据
- [x] 1.3 对照测量（纯 Python / 已有原生库 / Rust 直调 / Zoo+Rust 适配链路）；验证：四种链路端到端 P50/P95/P99 已留档
  - **2026-10-09 完成**：四链路对照（Modbus RTU 1/8/125 寄存器帧，n=3000/组合，同一次运行）落 `native/DECISION.md` 第三节 + `native/results/stage0_phase2_four_paths.json`；P50 加速 1.03x（no-go）/ 2.83x / 9.71x（go），P99 全改善（−20.9% / −57.1% / −89.2%）
- [x] 1.4 写 `native/DECISION.md`（沿用 bench/DECISION.md 格式）：任务选定、数据、go/no-go 门槛确认；验证：维护者明示「go」后才勾选后续章节
  - **2026-10-09 完成**：维护者确认门槛 **P50 ≥1.5x 且 P99 劣化 ≤5%**；结论 **go，附工作包络**——帧 ≥8 寄存器（≥21 字节）路由原生，更小帧留 Python 侧（P2 形态 1.10µs 已同机最优）

## 2. 契约与 Python 侧组件（前提：1.4 = go）

- [x] 2.1 新增 `zoo_framework/native/contract.py`：`NativeTaskContract` 数据类与 `NativeTaskError` 三族异常（`NativeInvalidInput` / `NativeTaskFailed` / `NativePanic`）；验证：契约字段完整性用例（spec「契约字段完整且语言无关」）
  - **完成记录**：`contract.py` 落地（数据类七字段 + `NativeTaskError` 基类三族）；验证 `tests/test_native_task_execution.py::TestContract`（字段完整、语言无关、三族同基）。**D6 键名漂移注记（2026-10-10）**：design.md 写 `native:contract_version` / `native:tasks`，实现为 `native:contractVersion`（native_params.py，camelCase 与框架既有键族风格一致）/ `native:task:<name>:maxInputBytes` 前缀拼装——spec delta 未键化这些名字，无规格冲突；两参数当前均无消费点（见 worker.md 配置表）
- [x] 2.2 新增 `zoo_framework/params/native_params.py`：`native:*` 键族三段解析（`enabled` 默认 False / `contract_version` / `tasks`）；验证：`tests/test_config_resolution.py` 新增用例全绿
  - **完成记录**：`native_params.py` 落地（`NATIVE_ENABLED` 默认 False / `NATIVE_CONTRACT_VERSION` / `NATIVE_TASK_PREFIX`）。**验证落点偏差**：解析用例落 `tests/test_native_task_execution.py::TestNativeParams`（与 test_config_resolution.py 同构的三段解析断言），未另开文件——解析语义已有等价覆盖
- [x] 2.3 新增 `zoo_framework/native/adapter.py`：加载扩展、`contract_version()` 与 `capabilities()` 握手比对、输入准备/输出转换、错误三族映射；扩展缺失/版本不匹配/能力不满足 → 执行前显式拒绝；验证：spec「未安装扩展时请求原生任务被明确拒绝」「契约版本不匹配被明确拒绝」两 Scenario 的用例红转绿
  - **完成记录**：`adapter.py` 落地；验证 `TestAdapterHandshake`（缺失/版本/能力/未注册任务四类显式拒绝）+ `TestAdapterConvertAndMap`（输入超限执行前拒绝、非三族异常兜 `NativePanic`）
- [x] 2.4 新增 `zoo_framework/native/worker.py`：`NativeTaskWorker` 继承既有生命周期，`_execute()` 委托 `adapter.prepare_input → execute → 转换输出`，结果交既有 hooks 与单一结算；验证：spec「原生任务成功时结果经单一结算点投递」「原生任务报错时错误映射进结算收口」用例（mock 派发侧按 assertion-integrity 调用时快照）
  - **完成记录**：`worker.py` 落地；验证 `TestNativeTaskWorker`（恰好一次投递经订阅收集、`error=` 分支不投成功空结果、hooks 全走）
- [x] 2.5 new file `zoo_framework/native/__init__.py` 暴露公共面（contract / adapter / worker / get_native_adapter）；验证：ruff + mypy 对新包零错误（mypy 为硬门禁）
  - **完成记录**：`__init__.py` 公共面（CONTRACT_VERSION / 三族异常 / NativeAdapter / NativeTaskWorker / get_native_adapter / reset_native_adapter）；ruff + mypy 零错误（本机门禁与 PR #104 CI 均绿）
- [x] 2.6 长任务释放 GIL 行为测试（fake adapter 模拟长执行）：验证 spec「原生长任务执行时控制线程可推进」；并发用例遵守「调用时快照」纪律（见 assertion-integrity）
  - **完成记录**：`test_long_running_task_releases_gil_placeholder`（fake adapter 时间驱动，验证 Python 侧契约：执行期间控制线程计数推进）；真扩展的 `py.allow_threads` detach 实现于 `native/src/lib.rs:56`，间接证据为 DECISION.md 第二组多线程伸缩数据（12 线程 5.87x）——真扩展 GIL 释放无直接观测用例（记录修正 2026-10-10，原表述过度声明）

## 3. Rust 扩展与首个真实任务

- [x] 3.1 建 `native/` 子目录：独立 `pyproject.toml`（maturin 后端）+ `Cargo.toml`（固定 PyO3 版本，按该版本核实 `Python::detach` 名称）+ hatchling 主包 exclude 验证；验证：`pip install -e ".[dev]"` 主路径不受影响，`python -m build` 主包不含 native 产物
  - **完成记录**：crate `native/`（maturin 后端，PyO3 0.23.5 经 `Cargo.lock` 固定；`Python::detach` 在 0.23 为 `py.allow_threads`，已按版本核实）；主包 wheel `packages=["zoo_framework"]` 天然不含 native 产物；`uv pip install --python .venv/Scripts/python.exe ./native` 安装成功且不动 uv.lock
- [x] 3.2 实现 `contract_version()` / `capabilities()` 常量暴露 + 输入/输出格式转换与三族错误结构；验证：Rust 单元测试（`cargo test`）三族错误可触发
  - **完成记录**：`cargo test` 11 绿；`into_py_err` 把 `InvalidInput`/`TaskFailed` 映射为 `NativeInvalidInput`/`NativeTaskFailed`，Rust panic 经 PyO3 → `NativePanic` 包装（adapter 职责）；`capabilities()` 返回空清单
- [x] 3.3 实现阶段 0 选定的真实任务（Rust 侧，detach 执行体不回调 Python）；验证：`cargo test` + 与 Python 侧等价样本比对语义一致
  - **完成记录**：`modbus_rtu.parse_response`（`native/src/modbus.rs`，纯 core 不依赖 pyo3，执行体经 `py.allow_threads` 释放 GIL 不回调 Python）；等价性：`tests/test_native_extension.py` 对 5 类样本帧（1/8/125 寄存器 + 两异常帧）与独立参考实现 `native/reference/modbus_rtu.py` 逐值一致
- [x] 3.4 扩展构建产物加载路径验证（本机有工具链则 skipif 放行）：契约握手、真任务执行、错误映射全链路；验证：`pytest` native 用例通过或显式 skip
  - **完成记录**：`tests/test_native_extension.py` 9 绿（加载/握手/契约字段/等价性/三族映射/执行前拒绝）；文件级 `pytest.importorskip`——扩展未安装时显式 skip，不伪装通过也不误报

## 4. 注册、配置与集成

- [x] 4.1 `native:enabled=True` 时经 `Master.register_worker` 注册 `NativeTaskWorker` 实例的接入代码路径；验证：测试内同名 Worker 注册后经 waiter 正常派发一例
  - **完成记录**：零框架代码新增——D5 构造期路径经「零参 `__init__` 子类」即通（`Master.register_worker` → `WorkerRegistry` 延迟实例化 → `waiter.add_worker`）；验证 `TestNativeRegistrationIntegration::test_construction_time_registration_via_master_dispatches_once`。`native:enabled` 开关语义属 `DualArmWorker`（adaptive 规格：声明原生臂时据此显式拒绝）；`NativeTaskWorker` 本身即显式 opt-in，不设二次开关
- [x] 4.2 运行期注册路径：`WorkerRegistry.register_instance` + `core.add_worker`；验证：运行期新增的 NativeTaskWorker 下一轮即被派发（既有派发逻辑回归不破）
  - **完成记录**：验证 `test_runtime_instance_registration_dispatched_next_round`——`register_instance` + `waiter.add_worker` 后下一轮 `execute_service` 恰好派发一次
- [x] 4.3 超时熔断与停机场景回归：验证 spec「超时只熔断不声称终止」「停机后不再接收新任务」「资源释放幂等且有限等」三 Scenario 用例
  - **完成记录**：`TestNativeStopSemantics` 三用例（线程池模型 + 阻塞 fake adapter 掌控「仍在执行」）。断言有效性注入验收（.claude/rules/assertion-integrity.md）：违规 1（不熔断）/3（mark_stopped 不置位）/4（join 忽略预算）各自变红后按 md5 逐字节还原；违规 2（execute_service 忽略 stopped）单层被纵深防御兜住（列表清空 + submit 拒绝），场景契约不破——停机用例断言的是外层可观测行为（stopped 标记 / 列表清空 / 执行数冻结）。**2026-10-10 补记（违规 5）**：5.2 新增的「错误不投成功空结果」直接断言（WaiterResultReactor 订阅收集 delivered 为空）经注入验收——错误路径包装空 WorkerResult 上报时断言变红（md5 9c7b04b4… 复原前/后逐字节一致）
- [x] 4.4 本机全量 pytest + ruff + mypy + bandit 通过；既有测试无回归；验证：CI 门槛本地等价命令零错误
  - **完成记录**：pytest 842 绿（新增 5 条）；ruff check 全过、`ruff format --check` 107 文件已格式化；mypy 107 文件零错误；bandit exit 0（`-c .bandit.yaml`）

## 5. 性能与正确性验收（阶段 2）

- [x] 5.1 同机同运行对照测量（冻结真实输入，非「循环到达标」替身）：单任务 / 小批 / 大批 / 饱和；验证：端到端 P50/P95/P99 + 吞吐 + 转换成本数据落档（结果写入 `native/DECISION.md` 附录）
  - **2026-10-10 完成**：`native/stage2_acceptance.py` 四形状（single 125reg / batch_small 8×1reg / batch_large 64×125reg / saturate 12 线程）同一次运行内测量，冻结帧组 + 固定迭代数，等价性前置检查通过后才测。结果：**9.87x / 1.07x / 10.22x / 7.49x**（吞吐 65,710 帧/s@单线程大帧），包络内 P99 全改善（−87% 以上）；转换占比 0.66。落档 `native/DECISION.md`「阶段 2 验收」附录 + `native/results/stage2_acceptance.json`
- [x] 5.2 覆盖正常/失败/超时后晚到结果/停机/重复关闭/资源残留行为验证；验证：各场景测试用例全绿
  - **2026-10-10 完成**：既有 TestNativeTaskWorker（正常/失败/hooks）+ TestAdapterHandshake（四类显式拒绝）+ TestNativeStopSemantics（超时熔断/停机新任务/幂等有界停机）之外，新增 `test_late_result_after_timeout_settles_once_without_residue`（熔断后晚到结果恰好一次投递、inflight 清零）。注入验收见 4.3；pytest 全绿
- [x] 5.3 原生 Windows / Linux / macOS 测量（有条件则做；WSL2 数字不作为 Linux 绝对开销依据）；验证：平台对照表格已记录
  - **2026-10-10 完成（有条件则做：本机仅 Windows）**：Windows 原生（10.0.26200，24T，CPython 3.13.14）已测；Linux/macOS 待 CI 原生构建（maturin/cargo 未在 GitHub Actions 配置，真扩展用例 CI 中显式 skip）后补齐。平台对照表格见 `native/DECISION.md` 阶段 2 附录；未使用 WSL2 数字

## 6. 文档、规格与归档（阶段 3）

- [x] 6.1 同步 `docs/`（原生任务使用与接入说明、可选安装说明）；验证：`pm` agent 文档比对审核通过
  - **2026-10-10 完成**：`docs/API_REFERENCE.md` 新增 NativeTaskWorker 章节（用法/契约/错误三族/可选安装/注册/单例入口）；`docs/ARCHITECTURE.md` 新增第 10 节（边界职责/单一结算/GIL 释放/测量结论）；三语站点 worker.md 在既有 NativeTaskWorker 章节上补「可选安装」段与 DualArmWorker 示例任务名更正。`pm` agent 文档比对审核已运行，发现 1🔴+2🟡+附带发现 A **均已修正**（🔴 输出解码失败时机标注三处更正 + contract.py docstring 根因；🟡 示例任务名/类图字段；A：`adaptive:explorationOverride` 两段键口径，API_REFERENCE 原写法会导致静默失效——已按实现消费点 `adaptive/policy.py` 更正），审核通过
- [x] 6.2 spec-syncer 核对 `openspec/specs/native-task-execution/spec.md` 合入与实现一致；验证：`spec-syncer` agent 差异清单为空
  - **2026-10-10 完成**：`spec-syncer` agent 核对——`openspec validate add-native-task-execution --strict` **通过**；13 个 Scenario → 测试映射表完成（8 直接支撑 + 需确认 4 项已处置：S6 已补「错误不投成功空结果」直接断言并注入验收、S11/S12 接受首版按构造保证（tasks 完成记录已显式注记）、2.6 失实记录已修正；S3 由 6.3 干净 venv 验证闭环）。无 🔴 项；归档 apply 清单 = 仅 `native-task-execution` 新能力目录，与既有规格无冲突（adaptive-scheduling 的前向引用转真实）
- [x] 6.3 未安装原生包时现有功能可用性验证（干净 venv 装 0.x 主包，native 关闭默认路径）；验证：spec「未安装扩展时既有功能不受影响」用例
  - **2026-10-10 完成**：临时 venv 离线安装主包 `zoo-framework==0.9.2b0`（uv 缓存构建，无 dev 附加、无原生扩展），验证脚本 6/6 通过——主包可导入、`zoo_framework_native` 缺席、`ensure_ready()` 与 `NativeTaskWorker._execute()` 均以 `NativeInvalidInput` 显式拒绝（指明缺的是扩展）、普通 Worker 经 `Master.register_worker` + `execute_service` 正常派发、状态机读写正常。配套证据：CI（无扩展环境）pytest 842 全绿即「既有功能不受影响」的套件级证明
- [x] 6.4 结果（版本、可复现入口、未完成项）回调 issue #88
  - **2026-10-10 完成**：回调评论已发布（含阶段 0–3 交付对照、9.87x/10.22x/7.49x 验收数据、未完成项：发行形态/CI Rust 工具链/native:enabled 角色重划/契约 v2 候选/后续扩展触发条件）
