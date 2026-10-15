"""Prometheus 文本端点 exporter 示例（变更 wire-svm-metrics / issue #246）。

**不装任何可选附加即可跑通**：只用标准库 `http.server` 与 `zoo_framework.observability`。
它演示执行事实接缝的用法——内核只生产事实，exporter 作为消费者注册观察回调，把每次执行
累加为 Prometheus 文本格式，经 `GET /metrics` 暴露。

运行（在仓库根目录）：

```bash
python example/observability/prometheus_endpoint.py
```

另开一个终端拉取指标（每约 1 秒执行计数递增）：

```bash
curl localhost:9111/metrics
```

按 Ctrl-C 停止。
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from zoo_framework.core import Master
from zoo_framework.observability import PrometheusTextExporter
from zoo_framework.workers import BaseWorker

PORT = 9111


class TickWorker(BaseWorker):
    """每秒打印一行的循环 Worker——供 exporter 观察其执行计数。"""

    def __init__(self) -> None:
        super().__init__({"name": "tick_worker", "is_loop": True, "delay_time": 1.0})
        self._round = 0

    def _execute(self) -> str:
        self._round += 1
        print(f"[tick_worker] round #{self._round}")
        return "tick"


class MetricsHandler(BaseHTTPRequestHandler):
    """把 exporter 渲染的 Prometheus 文本作为 `/metrics` 响应体。"""

    exporter: ClassVar[PrometheusTextExporter | None] = None

    def do_GET(self) -> None:
        if self.path != "/metrics":
            self.send_error(404, "only /metrics is served")
            return
        exporter = MetricsHandler.exporter
        body = (exporter.render() if exporter is not None else "").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Silence the default per-request stderr line."""


def main() -> None:
    """起一个 Master，并把执行事实经 Prometheus 文本端点暴露出去。"""
    exporter = PrometheusTextExporter()
    exporter.observe()
    MetricsHandler.exporter = exporter

    server = ThreadingHTTPServer(("127.0.0.1", PORT), MetricsHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # 只用中文不用 emoji：Windows 控制台默认 GBK，emoji 会直接抛 UnicodeEncodeError
    print(f"Prometheus 文本端点已启动：http://localhost:{PORT}/metrics（Ctrl-C 停止）")

    master = Master()
    master.register_worker("TickWorker", TickWorker)
    try:
        master.run()
    finally:
        exporter.close()
        server.shutdown()


if __name__ == "__main__":
    main()
