# tasks — add-native-task-execution

> 前置闸门（design D7）：阶段 0 未通过（未选定真实任务 / 未确认 go/no-go）时，第 3 组起的实现任务**不执行**；变更以「阶段 0 未通过」结论收尾，不归档为已实现。

## 1. 阶段 0：选真实任务并建立可证伪基线

- [x] 1.1 确认首个真实消费者任务候选（zoo-code-agent 工具循环或设备协议解析），记录业务等价判据与候选理由；产出维护者确认
  - **2026-10-09 重估结论**：维护者排除 zoo-code-agent（仅框架本身）；候选「事件管道排空循环」经链路剖析（1.2）证实 native 下沉收益低（单事件成本被 executor.submit 记账 31.9µs 主导，可下沉段仅 1–2µs）。事件管道优化改由独立 change 承接：`add-event-push-model` + `optimize-event-dispatch-batching`（均已规划完成）。native 线候选池如实更新：框架自身暂无现成 CPU 密集大任务；**首批真实消费者 = 下游使用方（如 adaptive 训练项目，未来NativeTaskWorker 消费）**；待下游任务实际出现后回到本条做业务等价判据确认
- [x] 1.2 剖析完整链路（输入到达 → 调度等待 → 排队 → 输入转换 → 任务执行 → 输出转换 → 结果接收），同一次运行内分段采集，遵守 bench/ 三条读数硬约束；验证：剖析记录含转换/编排占比与离散度
  - **2026-10-09 剖析记录**：候选「事件管道排空循环」逐段成本拆解见对话留档（出队 ~50ns / 过期+查找 ~µs / **executor.submit 31.9µs=唯一大头且不可跨语言下沉** / 等待有界）；结论——候选任务的可下沉段占比过低，native 化收益预期从「高」降为「低」。受控形态测量（任务体加速/伸缩）已另录 `native/DECISION.md` 第一组数据
- [ ] 1.3 对照测量（纯 Python / 已有原生库 / Rust 直调 / Zoo+Rust 适配链路）；验证：四种链路端到端 P50/P95/P99 已留档
- [ ] 1.4 写 `native/DECISION.md`（沿用 bench/DECISION.md 格式）：任务选定、数据、go/no-go 门槛确认；验证：维护者明示「go」后才勾选后续章节

## 2. 契约与 Python 侧组件（前提：1.4 = go）

- [ ] 2.1 新增 `zoo_framework/native/contract.py`：`NativeTaskContract` 数据类与 `NativeTaskError` 三族异常（`NativeInvalidInput` / `NativeTaskFailed` / `NativePanic`）；验证：契约字段完整性用例（spec「契约字段完整且语言无关」）
- [ ] 2.2 新增 `zoo_framework/params/native_params.py`：`native:*` 键族三段解析（`enabled` 默认 False / `contract_version` / `tasks`）；验证：`tests/test_config_resolution.py` 新增用例全绿
- [ ] 2.3 新增 `zoo_framework/native/adapter.py`：加载扩展、`contract_version()` 与 `capabilities()` 握手比对、输入准备/输出转换、错误三族映射；扩展缺失/版本不匹配/能力不满足 → 执行前显式拒绝；验证：spec「未安装扩展时请求原生任务被明确拒绝」「契约版本不匹配被明确拒绝」两 Scenario 的用例红转绿
- [ ] 2.4 新增 `zoo_framework/native/worker.py`：`NativeTaskWorker` 继承既有生命周期，`_execute()` 委托 `adapter.prepare_input → execute → 转换输出`，结果交既有 hooks 与单一结算；验证：spec「原生任务成功时结果经单一结算点投递」「原生任务报错时错误映射进结算收口」用例（mock 派发侧按 assertion-integrity 调用时快照）
- [ ] 2.5 new file `zoo_framework/native/__init__.py` 暴露公共面（contract / adapter / worker / get_native_adapter）；验证：ruff + mypy 对新包零错误（mypy 为硬门禁）
- [ ] 2.6 长任务释放 GIL 行为测试（fake adapter 模拟长执行）：验证 spec「原生长任务执行时控制线程可推进」；并发用例遵守「调用时快照」纪律（见 assertion-integrity）

## 3. Rust 扩展与首个真实任务

- [ ] 3.1 建 `native/` 子目录：独立 `pyproject.toml`（maturin 后端）+ `Cargo.toml`（固定 PyO3 版本，按该版本核实 `Python::detach` 名称）+ hatchling 主包 exclude 验证；验证：`pip install -e ".[dev]"` 主路径不受影响，`python -m build` 主包不含 native 产物
- [ ] 3.2 实现 `contract_version()` / `capabilities()` 常量暴露 + 输入/输出格式转换与三族错误结构；验证：Rust 单元测试（`cargo test`）三族错误可触发
- [ ] 3.3 实现阶段 0 选定的真实任务（Rust 侧，detach 执行体不回调 Python）；验证：`cargo test` + 与 Python 侧等价样本比对语义一致
- [ ] 3.4 扩展构建产物加载路径验证（本机有工具链则 skipif 放行）：契约握手、真任务执行、错误映射全链路；验证：`pytest` native 用例通过或显式 skip

## 4. 注册、配置与集成

- [ ] 4.1 `native:enabled=True` 时经 `Master.register_worker` 注册 `NativeTaskWorker` 实例的接入代码路径；验证：测试内同名 Worker 注册后经 waiter 正常派发一例
- [ ] 4.2 运行期注册路径：`WorkerRegistry.register_instance` + `core.add_worker`；验证：运行期新增的 NativeTaskWorker 下一轮即被派发（既有派发逻辑回归不破）
- [ ] 4.3 超时熔断与停机场景回归：验证 spec「超时只熔断不声称终止」「停机后不再接收新任务」「资源释放幂等且有限等」三 Scenario 用例
- [ ] 4.4 本机全量 pytest + ruff + mypy + bandit 通过；既有测试无回归；验证：CI 门槛本地等价命令零错误

## 5. 性能与正确性验收（阶段 2）

- [ ] 5.1 同机同运行对照测量（冻结真实输入，非「循环到达标」替身）：单任务 / 小批 / 大批 / 饱和；验证：端到端 P50/P95/P99 + 吞吐 + 转换成本数据落档（结果写入 `native/DECISION.md` 附录）
- [ ] 5.2 覆盖正常/失败/超时后晚到结果/停机/重复关闭/资源残留行为验证；验证：各场景测试用例全绿
- [ ] 5.3 原生 Windows / Linux / macOS 测量（有条件则做；WSL2 数字不作为 Linux 绝对开销依据）；验证：平台对照表格已记录

## 6. 文档、规格与归档（阶段 3）

- [ ] 6.1 同步 `docs/`（原生任务使用与接入说明、可选安装说明）；验证：`pm` agent 文档比对审核通过
- [ ] 6.2 spec-syncer 核对 `openspec/specs/native-task-execution/spec.md` 合入与实现一致；验证：`spec-syncer` agent 差异清单为空
- [ ] 6.3 未安装原生包时现有功能可用性验证（干净 venv 装 0.x 主包，native 关闭默认路径）；验证：spec「未安装扩展时既有功能不受影响」用例
- [ ] 6.4 结果（版本、可复现入口、未完成项）回调 issue #88
