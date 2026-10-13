# tasks — native-contract-v2

> **破坏性契约变更（主版本 1 → 2）；实施 MUST 经维护者批准。**
> **本变更只交付设计与规格，不实现代码**——第 1 节是本次成果，第 2 节是实施前置裁决，
> 第 3/4 节是实施阶段的清单，全部保持未勾选。

## 1. 规格与设计（本次交付）

- [x] 1.1 `specs/native-task-execution/spec.md` 写入 delta：MODIFIED「语言无关的原生任务执行契约」
      （`output_format` 扩为 `"{bytes,json,python}"` + 输出所有权/纯度约束）+ ADDED「契约主版本
      变更 MUST 显式拒绝不匹配的扩展」「execute 返回形状 MUST 由 output_format 决定」
      「性能证据 MUST 来自同一次运行内的四链路对照」
- [x] 1.2 `openspec validate native-contract-v2 --strict` 通过
- [x] 1.3 `design.md` 逐条回答 6 个问题：D1 主版本兼容策略 / D2 输出所有权与生命周期 /
      D3 `output_format` 取值扩展与迁移 / D4 三族错误语义 / D5 `execute` 签名冲击 / D6 性能验收口径
- [x] 1.4 破坏性与「需维护者批准」在 proposal / design / tasks 三处显著标注
- [x] 1.5 `native/DECISION.md` 增「契约 v2 候选（已立项提案）」一节，指向本变更

## 2. 维护者裁决（实施前置，未批准前不进入第 3 节）

- [ ] 2.1 裁决 Q1：契约主版本硬切换 vs 保留 v1 并只扩取值（design D1）
- [ ] 2.2 裁决 Q2：`"python"` 命名（vs `"dict"`）（design D3）
- [ ] 2.3 裁决 Q3：125reg 的 P50 改善门槛数值；是否把 `"python"` 作为默认推荐路径（design D6）
- [ ] 2.4 裁决 Q4：`native:contractVersion` 配置键的处置（design Open Questions）
- [ ] 2.5 批准实施

## 3. 实现（未开始）

- [ ] 3.1 `zoo_framework/native/contract.py`：`CONTRACT_VERSION` 1 → 2
- [ ] 3.2 `zoo_framework/native/adapter.py`：`convert_output` 增加 `"python"` 分支（纯数据校验后
      原样移交）；`execute` 去掉 `bytes(output)` 无条件强转；未知取值仍 `NativeInvalidInput`
- [ ] 3.3 `native/src/lib.rs` + `native/src/contract.rs`：`execute` 返回分派；`"python"` 分支在
      FFI 边界构造对象图（构造窗口有界，detach 期间不触碰 Python 对象）
- [ ] 3.4 本仓样例任务 `modbus_rtu.parse_response` 的契约切到 `output_format="python"`
      （纯 Python 参考实现本就返回 dict，逐值等价判据不变）
- [ ] 3.5 `native/template/**` 与 `native/validate_contract.py` 同步返还形状与机械校验
- [ ] 3.6 `docs/native-tasks.md` 的四个入口表 + 契约演进规则更新
- [ ] 3.7 扩展包 `native/pyproject.toml` minor 提升，且主包 `native` 附加范围收紧到
      `>=0.2,<0.3`（否则 pip 会装上一个会被拒的旧扩展）
- [ ] 3.8 按 `docs/native-release-runbook.md` 走一遍发布验证（CI 三平台 + 端到端安装）

## 4. 验证（未开始）

- [ ] 4.1 `cargo test`（`native/` 与 `native/template/`）全绿
- [ ] 4.2 `pytest tests/test_native_extension.py tests/test_native_task_execution.py`
- [ ] 4.3 三族错误映射回归 + 新增用例：`"python"` 输出形状违约归 `NativeInvalidInput`
      （不归 panic 族、不伪装成功）；版本不匹配双向拒绝
- [ ] 4.4 同一次运行内的四链路对照（P1/P2/P3/P4），结果落盘 `native/results/`
- [ ] 4.5 门槛判定：125reg 的 P50 改善达标且 P99 劣化 ≤5%、3reg 不劣化；未达则记 no-go、
      保留 v1、不归档实现
