## 1. 回归与实现

- [x] 1.1 在未修改的基线新增运行期准入回归用例：池 2 + reject 运行期新增必抛错且不纳入、queue
  照常接纳、expand 真实增补运行中的池、线程模型无容量一律接纳；确认 reject 与 expand 两例在修复
  前失败。
- [x] 1.2 `BaseWaiter.add_worker` 先经 `model.prepare_workers(候选列表)` 再 `core.add_worker`。
- [x] 1.3 `ThreadPoolModel.prepare_workers` 在容器已运行时按 `expand` 增补线程；抽出幂等的
  `_ensure_threads` 并让 `start` 复用。

## 2. 规格

- [x] 2.1 编写 proposal、design、`scheduler-model` delta spec 与 tasks，记录先裁决后写入与 expand
  在运行期真实生效的理由。

## 3. 验证

- [x] 3.1 聚焦用例与全量 `pytest` 通过。
- [x] 3.2 `ruff check zoo_framework`、`mypy zoo_framework` 干净。
- [x] 3.3 `openspec validate fix-runtime-registration-backpressure --strict` 通过。
