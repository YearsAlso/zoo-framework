# 提案：native-contract-v2 —— 原生扩展直出 Python 对象，省掉 JSON 编解码

## Why

`native/DECISION.md` 读数边界④与 `docs/ARCHITECTURE.md` 的测量结论点的是同一处浪费：
125reg 大帧端到端 ~9.8x 里，**转换/编排占 66%**，其中 **Rust 侧 JSON 构建 + Python 侧
`json.loads` 合计约 8µs**（P3 13.3µs − supp_rust_raw 5.1µs）。这 8µs 不产生任何业务价值：
它只是为了把执行体已经算好的结构，绕道「序列化成 UTF-8 JSON 字节 → 在 Python 侧再解析回
dict」才回到 Python。

契约 v1 把输出定为 `bytes`（约定为 JSON 文本），这条往返因此被写死在契约里。本提案把
「扩展在 FFI 边界直接构造并**移交**一个纯 Python 对象」变成契约的一等形态——这正是
`native/DECISION.md` 原文点名的候选：「契约 v2 若改为扩展直出 Python dict 可再省一截——
仅记录为候选，未实施（契约版本变更属新决策）」。本变更就是那次「新决策」的立项。

**这是破坏性契约变更**：契约主版本由 1 递增到 2，现存 v1 扩展在主版本不匹配时被**显式
拒绝**（不静默回退、不尽力兼容、不保留双版本并存的转换路径）。**实施 MUST 经维护者批准；
本次只交付设计与规格，不写代码。**

## What Changes

- 契约字段 `output_format` 的取值集合由 `{"bytes", "json"}` 扩为
  `{"bytes", "json", "python"}`：`"python"` 表示扩展在 FFI 边界构造并移交一个**纯 Python
  数据对象**（样例为 dict），框架侧不做任何编解码。
- 入口 `execute(task, payload)` 的**入参形状不变**（`(str, bytes)`）；返回形状由该任务契约的
  `output_format` 决定（`"bytes"`/`"json"` → 字节串，语义同 v1；`"python"` → 纯 Python 对象）。
- 适配器在输出边界按 `output_format` 分派：`"python"` MUST NOT 编解码，只做「纯数据对象图」
  校验后原样移交；MUST NOT 再对返回值做无条件强制转换（如无条件 `bytes(...)`）。
- 契约主版本递增到 2：适配器在握手期拒绝版本不匹配的扩展，错误同时给出两侧版本号。
- 本仓样例任务（`modbus_rtu.parse_response`）的契约切到 `"python"`——纯 Python 参考实现
  （`native/reference/modbus_rtu.py`）本来就返回 dict，两侧「逐值一致」的等价性判据不变。

## Non-Goals

- **不改输入侧**：`payload` 仍是 `bytes`。「扩展直接接收 Python 对象作为输入」是另一个变更。
- **不承诺零拷贝**：`"python"` 输出是扩展**新构造**的对象，不是 Rust 缓冲区的视图；
  `zero_copy` 能力仍声明为不支持（沿用 v1 的边界规则）。
- **不实现双主版本兼容**：不按配置在多个不兼容契约版本间选择、不为 v1 保留转换路径。
- **不新增错误族**：三族（InvalidInput / TaskFailed / Panic）语义不变（见 design D4）。
- **不承诺收益数字**：`~8µs` 是上限量级；净收益 MUST 实测（见 design D6）。
- **本次不写代码**：不动 `CONTRACT_VERSION`，不改 `zoo_framework/` 运行时代码与 `native/src`。

## Impact

- **契约（破坏性）**：`CONTRACT_VERSION` 1 → 2。扩展作者 MUST 同步递增自己的契约常量、改
  `execute` 的返回形状并重新构建——版本不匹配会被显式拒绝，不会「装作能用」。
- **代码（实施阶段，非本次）**：`zoo_framework/native/{contract,adapter}.py`、
  `native/src/{lib,contract,modbus}.rs`、`native/template/**`、`native/validate_contract.py`、
  `docs/native-tasks.md` 的四个入口表与演进规则。
- **依赖范围（实施阶段）**：主包 `native` 附加项的 `zoo-framework-native>=0.1,<0.2` 需随扩展包
  minor 版本提升收紧到 `>=0.2,<0.3`——契约版本与扩展包版本是两条曲线（native-distribution
  D5），但 v2 要求二者同步升，否则 pip 会给用户装上一个会被拒的旧扩展。
- **文档**：`native/DECISION.md` 增「契约 v2 候选（已立项提案）」一节；实施时同步更新
  `docs/ARCHITECTURE.md` 的「契约 v2 是优化候选」一句。
- **验收**：按 design D6 的口径做**同一次运行内**的四链路对照；未达门槛则如实记 no-go、
  不归档实现（保留 v1）。
