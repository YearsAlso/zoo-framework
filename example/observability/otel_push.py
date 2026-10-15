"""OTLP exporter 示例（变更 wire-svm-metrics / issue #246）。

**需要可选附加**：`pip install zoo-framework[otel]`。未安装时本示例会以指名安装方式的
显式错误退出（MUST NOT 静默回退）——这是与 `zoo-framework[native]` 一致的先例。

它演示执行事实接缝的另一条消费者路径：把每次执行推送到 OTLP/HTTP 端点（默认
`http://localhost:4318/v1/metrics`，即 OpenTelemetry Collector 的常用入口）。

运行（在仓库根目录）：

```bash
pip install zoo-framework[otel]
python example/observability/otel_push.py                 # 推到本地 Collector
ZOO_OTLP_ENDPOINT=http://collector:4318/v1/metrics \
    python example/observability/otel_push.py             # 推到指定端点
```

没有 Collector 也能跑：Worker 照常执行、指标在 exporter 内部累积，只是导出无人接收。
按 Ctrl-C 停止。
"""

import os

from zoo_framework.core import Master
from zoo_framework.observability import OtlpMetricExporter
from zoo_framework.workers import BaseWorker


class TickWorker(BaseWorker):
    """每秒打印一行的循环 Worker——供 exporter 观察其执行计数。"""

    def __init__(self) -> None:
        super().__init__({"name": "tick_worker", "is_loop": True, "delay_time": 1.0})
        self._round = 0

    def _execute(self) -> str:
        self._round += 1
        print(f"[tick_worker] round #{self._round}")
        return "tick"


def main() -> None:
    """起一个 Master，并把执行事实经 OTLP 推送出去。"""
    endpoint = os.environ.get("ZOO_OTLP_ENDPOINT")
    # 未装 `otel` 附加时，这一行抛出指名安装方式的 RuntimeError——显式失败，不静默降级
    exporter = OtlpMetricExporter(endpoint=endpoint, export_interval_millis=5000)
    exporter.observe()
    print(f"OTLP 导出已启动（端点：{endpoint or 'OTel 默认'}；Ctrl-C 停止）")

    master = Master()
    master.register_worker("TickWorker", TickWorker)
    try:
        master.run()
    finally:
        exporter.close()


if __name__ == "__main__":
    main()
