# 原生执行（Rust）

> **尚未发布。** `native/` 扩展已通过阶段性验收，但尚未发布到 PyPI，
> 因此当前无法通过 `pip install` 获得（见 issue #129）。本页描述的是已实现的契约。

契约：Python 保留编排与生命周期；扩展只承载**任务执行体**，执行期间释放 GIL。

::: zoo_framework.native.adapter.NativeAdapter
::: zoo_framework.native.adapter.get_native_adapter
::: zoo_framework.native.adapter.reset_native_adapter
::: zoo_framework.native.contract.NativeTaskContract
::: zoo_framework.native.contract.NativeContractDescriptor
::: zoo_framework.native.contract.CONTRACT_VERSION

## 样例任务

扩展随包携带一个样例任务 `modbus_rtu.parse_response`（Modbus RTU 响应帧解析）。
它是阶段 0 为判定「原生执行值不值得做」而选定的**首个真实业务任务**，作用有两重：
给出可复现的收益证据（工作包络：帧 ≥3 寄存器端到端 1.57x–9.63x；125 寄存器大帧
9.87x–10.22x；2 寄存器及更小帧留在 Python 侧不路由原生，见 `native/DECISION.md`），
以及充当两侧语义等价的对照体（`native/reference/modbus_rtu.py`，逐值比对）。

它是**样例负载，不是框架功能**：框架侧只按任务名分派，不认识任何具体任务。生产使用
SHOULD 在扩展侧注册自有任务名与契约；移除样例须同步摘除 `native/src/lib.rs`
（`execute` 的分支）与 `contract.rs`（任务常量与契约构造函数）中的注册点，框架侧
无需任何改动。

## 错误分类

::: zoo_framework.native.contract.NativeTaskError
::: zoo_framework.native.contract.NativeInvalidInput
::: zoo_framework.native.contract.NativeTaskFailed
::: zoo_framework.native.contract.NativePanic
