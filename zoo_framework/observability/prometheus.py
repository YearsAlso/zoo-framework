"""Prometheus 文本格式 exporter（变更 wire-svm-metrics / issue #246）。

以执行事实接缝的**消费者**身份存在：注册一个观察回调，把每次执行累加成计数与耗时
直方摘要，再渲染为 Prometheus 文本展示格式，供任意 HTTP 端点拉取。

**仅标准库**——不引入 `prometheus_client` 之类的第三方包，因此不装任何可选附加即可
跑通（`example/observability/prometheus_endpoint.py` 是端到端示例）。
"""

import threading
from typing import Any

from zoo_framework.core.execution_metrics import ExecutionFact, ExecutionObserverRegistry


class PrometheusTextExporter:
    """把执行事实导出为 Prometheus 文本格式。

    Attributes:
        namespace: 指标名前缀（默认 ``zoo``）
    """

    def __init__(self, namespace: str = "zoo") -> None:
        """Initialize the exporter (not yet observing; call ``observe()``).

        Args:
            namespace: the metric-name prefix
        """
        self.namespace = namespace
        self._lock = threading.RLock()
        # worker 名 -> {execute_count, error_count, total_duration}
        self._counters: dict[str, dict[str, float]] = {}
        self._registry = ExecutionObserverRegistry()

    def observe(self) -> None:
        """Start observing execution facts (idempotent per instance)."""
        self._registry.observe(self._on_fact)

    def close(self) -> None:
        """Stop observing; the accumulated counters stay readable."""
        self._registry.unobserve(self._on_fact)

    def _on_fact(self, fact: ExecutionFact) -> None:
        """Seam callback: fold one execution fact into the counters.

        Args:
            fact: one completed execution's immutable fact
        """
        with self._lock:
            entry = self._counters.setdefault(
                fact.worker_name, {"execute_count": 0, "error_count": 0, "total_duration": 0.0}
            )
            entry["execute_count"] += 1
            entry["total_duration"] += fact.duration
            if not fact.success:
                entry["error_count"] += 1

    def snapshot(self) -> dict[str, dict[str, float]]:
        """A copy of the accumulated counters (diagnostics / assertions).

        Returns:
            worker name -> {execute_count, error_count, total_duration}
        """
        with self._lock:
            return {name: dict(values) for name, values in self._counters.items()}

    def render(self) -> str:
        """Render the Prometheus text exposition format.

        Returns:
            The text body (``# HELP`` / ``# TYPE`` + one line per series).
        """
        snapshot = self.snapshot()
        ns = self.namespace
        lines = [
            f"# HELP {ns}_worker_execute_count Total executions completed per worker.",
            f"# TYPE {ns}_worker_execute_count counter",
        ]
        for name in sorted(snapshot):
            lines.append(
                f'{ns}_worker_execute_count{{worker="{_escape(name)}"}} '
                f"{_num(snapshot[name]['execute_count'])}"
            )
        lines += [
            f"# HELP {ns}_worker_error_count Failed executions per worker.",
            f"# TYPE {ns}_worker_error_count counter",
        ]
        for name in sorted(snapshot):
            lines.append(
                f'{ns}_worker_error_count{{worker="{_escape(name)}"}} '
                f"{_num(snapshot[name]['error_count'])}"
            )
        lines += [
            f"# HELP {ns}_worker_execute_seconds_total Cumulative execution seconds per worker.",
            f"# TYPE {ns}_worker_execute_seconds_total counter",
        ]
        for name in sorted(snapshot):
            lines.append(
                f'{ns}_worker_execute_seconds_total{{worker="{_escape(name)}"}} '
                f"{snapshot[name]['total_duration']!r}"
            )
        return "\n".join(lines) + "\n"


def _escape(label_value: str) -> str:
    """Escape a Prometheus label value (backslash, quote, newline)."""
    return label_value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _num(value: Any) -> str:
    """Render a counter as an integer-looking token when it is whole."""
    return str(int(value)) if float(value).is_integer() else repr(value)
