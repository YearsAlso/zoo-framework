# Tasks: add-adaptive-scheduling

> **⚠️ 状态：已延后（维护者 2026-10-09 决定）**——任务清单随整条 ML 线延后冻结，
> 不进入实施；理由与重启条件见 proposal.md 文首状态块。特征导出机制（必要前提）
> 的设计结论已保留在 design.md「维护者决定记录」。

## 1. 契约常量与参数层

- [ ] 1.1 新建 `zoo_framework/core/adaptive/schema.py`：`SCHEMA_V1`（特征名列表 + 版本常量 `FEATURE_LOG_SCHEMA_V = 1` / `MODEL_FORMAT_V = 1`）
- [ ] 1.2 新建 `zoo_framework/params/adaptive_params.py`：`AdaptiveParams`（ADAPTIVE_ENABLED / FEATURE_LOG_PATH / MODEL_PATH / LOG_FLUSH_THRESHOLD / EXPLORATION，lazy import 纪律），`params/__init__.py` 导出
- [ ] 1.3 测试：嵌套 config 解析（`{"adaptive": {...}}`）、falsy 值尊重（空字符串 modelPath = 无模型）、缺省保守默认（复用 test_config_resolution 形态；`importlib.import_module` 取模块的已知陷阱）

## 2. 特征与日志（框架写入侧）

- [ ] 2.1 新建 `zoo_framework/core/adaptive/profile.py`：`TaskProfile`（duration_ewma / error_rate_ewma / input_bytes_ewma，O(1) 更新，`threading.Lock`）
- [ ] 2.2 新建 `zoo_framework/core/adaptive/feature_log.py`：`FeatureLog`（内存缓冲 + 阈值批量 append JSONL + flush() + degraded 标记；record() O(1)；记录 schema_v 与实际执行路径）
- [ ] 2.3 登记 `FeatureLog` 进 `zoo_framework/core/process_state.py` CARRIERS
- [ ] 2.4 测试：EWMA 更新正确性、缓冲阈值触发写盘、写失败 degraded 后不再反复尝试、日志含 schema_v、并发 record 无交错损坏

## 3. 权重加载与推理

- [ ] 3.1 新建 `zoo_framework/core/adaptive/inference.py`：`LinearSoftmax`（从 checkpoint dict 加载：format_v/schema_v/checksum 三件套校验、score 点积、softmax 采样、`exploration` ε）；校验失败显式拒绝
- [ ] 3.2 新建 `zoo_framework/core/adaptive/scheduler.py`：`AdaptiveScheduler` 模块级单例（`get_adaptive_scheduler()`/`reset_adaptive_scheduler()`），`decide(worker_name)` → `"native"|"default"`；无模型/modelPath 空 → 恒 default；native 臂受 `native:enabled` 门控；`reload()` 重载入口
- [ ] 3.3 checksum 一致性生成器：训练项目会用到同款 hash 逻辑，提供 `compute_checksum(payload)` 供测试与文档说明（训练项目复刻同一算法，签名写入 spec）
- [ ] 3.4 登记 `AdaptiveScheduler` 进 CARRIERS
- [ ] 3.5 测试：兼容权重加载成功推理、版本不匹配/校验和错误/文件缺失显式拒绝、schema 维度对齐、无模型恒 default、native 未启用退化、reload 失败保持旧状态、ε 探索分布（固定种子统计断言）、线程安全（并发 decide/update）

## 4. 接线（挂点最小侵入）

- [ ] 4.1 `WorkerDispatchCore.begin`：登记后派发前查 `decide()`，决策与实际路径写登记项扩展字段；异常 fail-open 用默认路径（try/except 全包）
- [ ] 4.2 `WorkerDispatchCore.settle`：投递完成后 try/except 包裹 `FeatureLog.record(...)`（实测时长/错误/输入大小/队列深度 + EWMA 值 + chosen 与实际路径）；不改投递/盖章语义
- [ ] 4.3 测试：挂点消费行为（决策被采纳/异常 fail-open/记录字段完整）、关闭开关时 begin/settle 路径与合入前等价（不进 adaptive 分支、不取锁）、结算恰好一次语义不变（复用 test_scheduler_model 形态）

## 5. 端到端验收

- [ ] 5.1 集成场景：混合任务类运行 → 特征日志落盘内容正确（任务标识/特征/实际路径），无模型阶段全部走默认路径
- [ ] 5.2 加载手工构造兼容 checkpoint → 指向 native 的任务类被派往 native（native 启用）、其余保持默认
- [ ] 5.3 fail-open 端到端：决策器注入异常，任务仍成功完成、结果正确、日志不受损
- [ ] 5.4 性能验收：恒默认推理下派发路径延迟增量 < 2µs（本机参考形态；bench 同次运行内对照）
- [ ] 5.5 全量门禁：pytest 全绿、ruff/mypy 零错、`openspec validate add-adaptive-scheduling --strict` 通过

## 6. 训练项目契约与文档

- [ ] 6.1 docs/ 更新：adaptive 一节——特征 schema 契约、checkpoint 格式规范（字段/checksum 算法），写明训练项目以独立仓库承建、消费本契约
- [ ] 6.2 `openspec validate --strict` + pm 文档一致性审核，随后 `/opsx:archive`
- [ ] 6.3 归档后由 spec-syncer 核对 `openspec/specs/adaptive-scheduling/spec.md` 与实现一致
- [ ] 6.4 （后续，不在本变更）训练项目立项后：把特征 JSONL 喂训练、产出首个 checkpoint 走通全闭环；Rust 训练下沉登记到 `add-native-task-execution` 的候选池
