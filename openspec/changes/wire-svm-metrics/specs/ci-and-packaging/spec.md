## ADDED Requirements

### Requirement: 观测导出面 MUST 为可选附加且不加重默认负担

观测导出（OTel / Prometheus 等）SHALL 以**可选附加**（主包的一个 extra）与**可运行示例**
提供，MUST NOT 进入默认依赖；未安装该附加时框架行为 MUST 与安装前一致。仓库 SHALL 至少提供
一个**不依赖任何第三方包即可跑通**的 exporter 示例，使「接缝可用」有可执行证据。示例 MUST
可被实际执行，且 MUST NOT 从构建产物路径导入或以与公开接口不符的方式构造框架对象。

#### Scenario: 默认依赖不含导出上游

- **WHEN** 读取 `pyproject.toml` 的默认 `dependencies` 与可选附加清单
- **THEN** 导出上游包只出现在可选附加中，默认依赖不含它们

#### Scenario: 至少一个 exporter 示例可跑通

- **WHEN** 安装框架（不装任何可选附加）并运行仓库提供的 exporter 示例
- **THEN** 示例启动成功并可被读取到指标输出，不需要任何第三方导出库
