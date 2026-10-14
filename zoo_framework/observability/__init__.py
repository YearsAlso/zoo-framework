"""观测导出面（变更 wire-svm-metrics / issue #246）。

内核只生产执行事实（`ExecutionFact`），去向由消费者决定。本包提供把事实导出到外部
可观测性栈的 exporter，作为**可选面**存在：

- `PrometheusTextExporter`：**仅标准库**，把事实累加成 Prometheus 文本格式，可由
  任意 HTTP 端点拉取——不装任何可选附加即可用。
- `OtlpMetricExporter`：走 OTLP 推送到你的可观测性栈，需要可选附加
  `zoo-framework[otel]`；未安装时显式报错并指名安装方式（不静默回退）。

默认依赖不因此变重；不用观测导出的人不引入任何第三方包。
"""

from .otel import OtlpMetricExporter
from .prometheus import PrometheusTextExporter

__all__ = ["OtlpMetricExporter", "PrometheusTextExporter"]
