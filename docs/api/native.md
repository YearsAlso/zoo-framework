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

## 错误分类

::: zoo_framework.native.contract.NativeTaskError
::: zoo_framework.native.contract.NativeInvalidInput
::: zoo_framework.native.contract.NativeTaskFailed
::: zoo_framework.native.contract.NativePanic
