"""OTLP exporter（变更 wire-svm-metrics / issue #246）。

以执行事实接缝的**消费者**身份存在：注册一个观察回调，把每次执行累加进 OpenTelemetry
的计数器与直方图，经 OTLP 推送到你的可观测性栈。

上游依赖（OTel SDK + OTLP HTTP exporter）只在**可选附加**里声明，故本模块**惰性
import**它们：未安装时抛出指名安装方式的显式错误，MUST NOT 静默回退（与
`zoo-framework[native]` 同一先例）。
"""

from typing import Any

from zoo_framework.core.execution_metrics import ExecutionFact, ExecutionObserverRegistry

#: 缺可选附加时的显式提示——指名安装路径，不让人去猜
OTEL_EXTRA_HINT = (
    "the OTLP exporter requires the optional extra; install it with "
    "`pip install zoo-framework[otel]`"
)


def _load_otel() -> tuple[Any, Any, Any, Any]:
    """Lazily import the OTel SDK + OTLP HTTP exporter.

    Returns:
        ``(opentelemetry.metrics, MeterProvider, PeriodicExportingMetricReader,
        OTLPMetricExporter)``

    Raises:
        RuntimeError: the ``otel`` extra is not installed (message names the
            install command; MUST NOT silently fall back)
    """
    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    except ImportError as e:
        raise RuntimeError(f"{OTEL_EXTRA_HINT} (missing: {e.name})") from e
    return metrics, MeterProvider, PeriodicExportingMetricReader, OTLPMetricExporter


class OtlpMetricExporter:
    """把执行事实经 OTLP 推送到可观测性栈。

    Attributes:
        namespace: 指标名前缀（默认 ``zoo``）
    """

    def __init__(
        self,
        endpoint: str | None = None,
        export_interval_millis: int = 60000,
        namespace: str = "zoo",
    ) -> None:
        """Build the meter provider and the three instruments.

        Args:
            endpoint: the OTLP/HTTP metrics endpoint; None uses the OTel
                default (``http://localhost:4318/v1/metrics``)
            export_interval_millis: the periodic export interval
            namespace: the metric-name prefix

        Raises:
            RuntimeError: the ``otel`` extra is not installed
        """
        _, meter_provider_cls, reader_cls, exporter_cls = _load_otel()

        exporter = exporter_cls(endpoint=endpoint) if endpoint else exporter_cls()
        reader = reader_cls(exporter, export_interval_millis=export_interval_millis)
        self._provider = meter_provider_cls(metric_readers=[reader])
        meter = self._provider.get_meter("zoo_framework")

        self.namespace = namespace
        self._execute = meter.create_counter(
            f"{namespace}.worker.execute.count",
            description="Total executions completed per worker.",
        )
        self._error = meter.create_counter(
            f"{namespace}.worker.error.count",
            description="Failed executions per worker.",
        )
        self._duration = meter.create_histogram(
            f"{namespace}.worker.execute.duration",
            unit="s",
            description="Execution duration per worker.",
        )
        self._registry = ExecutionObserverRegistry()

    def observe(self) -> None:
        """Start observing execution facts."""
        self._registry.observe(self._on_fact)

    def close(self) -> None:
        """Stop observing and shut the meter provider down (flushes pending exports)."""
        self._registry.unobserve(self._on_fact)
        self._provider.shutdown()

    def _on_fact(self, fact: ExecutionFact) -> None:
        """Seam callback: record one execution fact on the OTel instruments.

        Args:
            fact: one completed execution's immutable fact
        """
        attributes = {"worker": fact.worker_name}
        self._execute.add(1, attributes)
        self._duration.record(fact.duration, attributes)
        if not fact.success:
            self._error.add(1, attributes)
