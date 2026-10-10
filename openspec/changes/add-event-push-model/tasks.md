# Tasks: add-event-push-model

## 1. 参数与通道侧

- [ ] 1.1 `zoo_framework/params/event_params.py`：新增 `PUSH_MODEL_ENABLED`（`event:pushModelEnabled`，默认 False）与 `PUSH_FALLBACK_TIMEOUT`（`event:pushFallbackTimeout`，默认 1.0）
- [ ] 1.2 `zoo_framework/event/event_channel.py`：懒创建 `threading.Condition`（开关门控）+ `push_event` / `dispatch` 成功后 `notify_all()`（入队成功才通知）
- [ ] 1.3 测试：通知在入队后发出（fake 条件变量录制调用）、关闭时 Condition 不被创建、回队路径同样通知

## 2. 消费侧挂起

- [ ] 2.1 `zoo_framework/workers/event_worker.py`：排空后（全部通道空且开关开）对所有通道 Condition `wait(timeout)`；唤醒/超时后走正常排空（消费主体复用既有路径）
- [ ] 2.2 测试：挂起与唤醒端到端（生产者入队et消费者消费）、兜底超时后恢复扫描、推模型关闭时走既有心跳轮询（行为等价断言）

## 3. 语义守护

- [ ] 3.1 测试：事件去向恰好其一（投递/回队/死信）在推模型开/关两态下一致（复用既有 event 测试形态）
- [ ] 3.2 关闭零影响断言：无 Condition 分配、生产路径无新增分支开销（可用源码级断言或行为等价）

## 4. 验收与归档

- [ ] 4.1 端到端：开启后空闲期为零扫描（挂起）、事件入队到消费延迟 < 心跳间隔
- [ ] 4.2 全量门禁：pytest / ruff / mypy / `openspec validate add-event-push-model --strict`
- [ ] 4.3 docs/ 更新事件一节；`/opsx:archive` 后 spec-syncer 核对
