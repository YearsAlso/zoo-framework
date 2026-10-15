# tasks — wire-svm-metrics

## 0. 维护者已裁定的四条（采用值 + 依据）

> 如有异议，维护者可在实现前否决。

| 原 Open Question | 采用值 | 依据 |
|---|---|---|
| 指标清单要不要先写进 spec | **只定「接通 + 接缝」，清单随后**：先把 `execute_count` 与健康判据做成真实值，其余指标留给消费方驱动；spec 里不冻结尚未有消费方校验的完整指标清单 | 无消费方校验的清单会漂移，且会变成「声明了没人用」的下一处静默；先让最小事实链路真实 |
| exporter 放哪里 | **本仓库可选依赖 + 示例**：新增 extra `otel`，`pip install zoo-framework[otel]`；不装则一切如旧 | 与 `zoo-framework[native]` 同一先例（可选附加只提供发现路径，默认「纯 Python、零依赖」不变） |
| 接缝形态 | 内核只**生产事实**、不决定去哪；形态**参照既有的 `observe_state` / 状态 effect 的路子** | 与既有扩展点同构，不另造一套观察者机制（见 design D1） |
| 指标身份口径 | 以 `worker.registry_name` 对齐（默认 Worker 与注册表键相同，对外 key 形状不变） | 派发侧只能看到 `registry_name`；否则事实命中不了 SVM 条目、仍恒零（见 design D3） |

## 1. 规格（spec-first）

- [x] 1.1 `specs/worker-lifecycle/spec.md`：REMOVED 旧日志如实性判据 + ADDED 监控日志与接通状态一致 /
      执行事实接缝 / 健康报告反映真实事实
- [x] 1.2 `specs/ci-and-packaging/spec.md`：ADDED 观测导出面 MUST 为可选附加且不加重默认负担
- [x] 1.3 `specs/docs-consistency/spec.md`：REMOVED 旧「如实标注未接通」判据 + ADDED 健康监控宣称
      MUST 与运行实况一致
- [x] 1.4 `specs/docs-roadmap/spec.md`：MODIFIED roadmap 与 README 口径一致 + 已立项互链 issue
- [x] 1.5 `specs/ai-discoverability/spec.md`：MODIFIED llms.txt / README FAQ 的健康监控口径
- [x] 1.6 `openspec validate wire-svm-metrics --strict` 通过

## 2. 内核实现（接缝 + 接通）

- [x] 2.1 新增 `zoo_framework/core/execution_metrics.py`：`ExecutionFact`（frozen）+ 进程级
      `ExecutionObserverRegistry`（`observe` / `unobserve` / `observers` / `emit`）
- [x] 2.2 `core/waiter/dispatch_core.py` 的 `settle` 在唯一结算收口产出并发射 `ExecutionFact`
      （耗时取登记项的单调起点；成败 = 结算无错误 **且** 结果未标记失败——`BaseWorker.run`
      把执行体异常封进结果而不外抛（#228），只看 `error` 会把失败一律记成成功）
- [x] 2.3 `core/master.py`：SVM 在 `start_monitoring` 注册、`stop_monitoring` 注销观察回调；
      注册与健康查询按 `worker.registry_name` 对齐；更新与实况不符的日志文案
- [x] 2.4 `SVMWorker` 未被启用（`enable_svm=False`）时零观察者、行为不变

## 3. 导出面（可选附加 + 示例）

- [x] 3.1 新增 `zoo_framework/observability/`：`PrometheusTextExporter`（仅标准库）与
      `OtlpMetricExporter`（惰性 import，缺附加时显式报错指名 `pip install zoo-framework[otel]`）
- [x] 3.2 `pyproject.toml`：新增 `otel` 可选附加（OTel SDK + OTLP exporter）；默认
      `dependencies` 不变
- [x] 3.3 新增 `example/observability/prometheus_endpoint.py`（标准库 `http.server`，
      不装附加即可跑）与 `example/observability/otel_push.py`（需附加）；`example/README.md` 增行

## 4. 测试

- [x] 4.1 `tests/test_execution_metrics.py`：接缝的注册收到事实 / 未注册行为不变 / 注销后不再收到 /
      事实不可变（写入即报错）
- [x] 4.2 健康报告用例：真实调度下 `execute_count` 非零且与实际一致；失败执行计入 `error_count`；
      未执行时如实为零
- [x] 4.3 exporter 用例：Prometheus 文本渲染含真实计数；示例端到端可跑通（进程内起
      `ThreadingHTTPServer` 拉 `/metrics`）；OTLP 缺附加时显式报错（阻断 import 而非依赖
      「本机恰好没装」）
- [x] 4.4 更新措辞契约测试（预期连带修改）：`tests/test_quiet_default_logs.py` 的 SVM 措辞、
      `tests/test_doc_consistency.py` 的 `_SVM_CLAIM_SITES` / `_STALE_HEALTH_MARKERS`、
      `tests/test_agent_discoverability.py` 的健康监控话题

## 5. 文档口径同步

- [x] 5.1 README.md / README.zh.md：能力表该行由 ⚠️ 改 ✅
- [x] 5.2 `llms.txt` / `AGENTS.md` / `docs/ARCHITECTURE.md` / `docs/README.md` 同步
- [x] 5.3 `docs/internal/business-plan.md`：去掉已过期的「指标链路未接通」限定
- [x] 5.4 `docs/contributing/roadmap.md`：「健康监控指标链路接通」与「可观测性导出」由 Later
      移入 Next，互链 issue #246
- [x] 5.5 `CHANGELOG.md` 的 `[Unreleased]` 补 Added / Changed 条目

## 6. 门禁与验收

- [x] 6.1 全量 `pytest` 通过：改动前 **1195 passed**（`git archive HEAD` 的纯净副本实测），
      改动后 **1217 passed**（+20 新用例 +4 `test_no_class_replacement` 扫描到新增模块
      -2 健康监控从「未实现」话题表移除）
- [x] 6.2 `ruff check zoo_framework`、`ruff check tests`、`ruff format --check zoo_framework tests`
      （除 5 个既有文件的 format 漂移外无新增）
- [x] 6.3 `mypy zoo_framework` 零新增错误（`Success: no issues found in 111 source files`）
- [x] 6.4 断言注入验证：VIOLATION-A（`start_monitoring` 不注册观察者）红 3 条；VIOLATION-B
      （`emit` 丢弃已注册回调）红 12 条；两处均按 md5 逐字节还原
