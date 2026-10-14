# Proposal: fix-runtime-registration-backpressure

## Why

issue #233 实锤：运行期注册的 Worker 绕过背压。启动期 muster（`BaseWaiter.call_workers`）会先经
`model.prepare_workers` 做容量准入、再建容器；但运行期 `BaseWaiter.add_worker` 直接
`core.add_worker` 追加进调度列表，**从不经过容量准入**。实测：池尺寸 2 + `reject` 策略下，运行期
注册 5 个 Worker 不报错、全部执行——`reject` 本应拒绝超容量请求。调用方配置了 `reject` 却得到
「静默全收」，配置与实际行为不一致且无任何提示，正是仓库反复禁止的「静默降级」。

## What Changes

- `BaseWaiter.add_worker` 走与启动期相同的容量准入：先把**候选**调度列表交给
  `model.prepare_workers` 裁决，被拒（`reject` 策略下超容量）时抛 `ValueError`，被拒的 Worker
  MUST NOT 进入调度列表。
- `ThreadPoolModel.prepare_workers` 在容器**已在运行**时把 `expand` 放宽后的生效容量真正应用到
  活的池（增补线程），避免「只改数字、没有效果」的静默 no-op；该增补经幂等的 `_ensure_threads`
  完成，`start` 复用它。
- 线程模型无容量概念，运行期注册仍一律接纳；`queue` 策略仍照常接纳（超出的排队）。
- 停机语义不变：停机后运行期注册不重建容器、不产生新派发（准入只在容器存在时才增补线程）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `scheduler-model`：新增「背压容量准入 MUST 同时约束启动期与运行期注册」——运行期新增须受同一
  背压策略裁决；`reject` 明确拒绝、`queue` 排队、`expand` 对运行中的池真实放宽。

## Impact

- **代码**：`zoo_framework/core/waiter/base_waiter.py`（`add_worker` 准入）、
  `zoo_framework/core/waiter/scheduler_model.py`（`prepare_workers` 运行期放宽 + `_ensure_threads`
  + `start` 复用）。
- **测试**：`tests/test_scheduler_model.py` 新增 `TestRuntimeAdmission`（4 例）：reject 拒绝、
  queue 接纳、expand 真实增补、线程模型无容量。
- **规格**：`openspec/changes/fix-runtime-registration-backpressure/specs/scheduler-model/spec.md`。
- **无新增依赖**；不改变 `SchedulerModel` 六项契约声明的取值。
- **相邻现象（不在本变更范围）**：`Master.register_worker` 在准入被拒时，类已写入注册表但未进入
  调度列表——注册表与调度列表之间的原子性属 `Master` 层，本变更只保证调度侧「被拒即不纳入、不
  静默」。
