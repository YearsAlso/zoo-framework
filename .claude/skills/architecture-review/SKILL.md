---
name: architecture-review
description: 架构审查 Skill — 从包结构与分层、依赖方向与单例注册、设计模式与 SOLID、Python 并发最佳实践、技术选型、数据访问与持久化、横切关注点、可测试性 8 个维度审查变更方案，供 reviewer 在架构/依赖/单例注册/技术选型变更时调用
---

# Architecture Review — 架构审查

从技术架构视角审查变更方案，确保代码变更符合架构设计原则、Python 3.13+ 并发最佳实践和项目技术栈约束。reviewer 在变更涉及架构/依赖/`@cage` 单例注册/技术选型时调用本 skill。

## 审查维度

### 1. 包结构与分层架构
- 分层正确：`core/`（内核）不依赖具体 Worker 业务实现；`utils/`、`constant/` 稳定层不反向依赖易变层
- 新增类型是否放在正确的包（Worker → `workers/`、事件 → `event/`、队列 → `fifo/`、反应堆 → `reactor/`、状态机 → `statemachine/`、参数 → `params/`）
- 包内职责单一，跨包交互经抽象而非直接耦合
- 模块命名与目录一致，无循环 import

### 2. 依赖方向与单例/注册机制
- `@cage` 单例使用是否恰当（缓存单例 keyed by 类名，进程级共享），是否扩大了全局可变状态面
- `WorkerRegistry`（新）与 `WorkerRegister`（legacy）双注册体系：新代码应走 `WorkerRegistry`（`Master` 使用的），避免混淆
- `@worker`/`@event` 装饰器是否在正确的导入时机注册（params 惰性导入约束）
- 依赖通过构造函数注入，避免在方法内直接实例化外部依赖（绕过注册/DI 的反模式）

### 3. 设计模式与 SOLID 原则
- SRP：类职责是否单一，有无"上帝类"（如 Master 承担过多）
- OCP：扩展点设计是否合理（`SchedulerModel`、`StateIndexFactory`、`PersistenceStrategy`、`Plugin` 等既有缝是否被复用而非另起炉灶）
- LSP：继承关系语义是否正确（Worker 子类是否遵守 `run()`/`_execute()` 契约）
- ISP：是否强依赖不需要的方法
- DIP：高层是否依赖抽象而非具体实现

### 4. Python 并发最佳实践
- 三条并发路径边界清晰：`threading`（worker 线程）、`asyncio`（`perform()` 循环）、`gevent`（事件管道，属待移除项）
- 阻塞调用不跑进 asyncio 事件循环；线程 daemon 化或显式 join（`zoo_thread`）
- 锁使用是否正确（`lock/`、`ThreadSafeDict`）；有无死锁/竞态；`multiprocessing.Lock` vs `threading.RLock` 选型（bench 结论：多数场景 RLock 更快）
- `is_loop` 方法/属性陷阱（见 python-syntax-review 维度 4）是否被正确规避
- GIL 认知：CPU 密集不靠多线程提速；性能结论须有 bench 依据

### 5. 技术选型与第三方依赖
- 新增依赖是否必要（优先复用现有栈），是否走 openspec change + ADR
- 依赖版本一致性（`pyproject.toml` / `uv.lock` / `requirements*.txt` 同步）
- 是否引入与现有栈冲突的库；gevent 依赖方向（计划移除，避免新增对其耦合）
- Rust 引入：必须回应 `bench/DECISION.md` no-go 结论与再评估条件，否则 ❌

### 6. 数据访问与持久化
- pickle 存档路径：原子写（`.tmp` + `os.replace`）、校验和、滚动备份（backups/ ≤5）是否保持
- `StateIndex` 后端选择（`ThreadSafeDict` 默认）与并发安全
- 反序列化安全（见 security-review）、跨版本兼容
- 热路径队列选型（`BaseFIFO` vs `deque`）是否有性能依据

### 7. 横切关注点
- 日志：关键节点是否结构化日志（`utils/structured_log.py`、`conf/log_config.py`），错误是否带 topic/worker 上下文
- 异常策略：异常类型选择、catch 范围、fail-fast（存档损坏/配置缺失）
- 配置管理：敏感/非敏感配置分离，配置键经 `ParamsPath` + aliases 解析
- 插件系统：新扩展点是否走 `PluginManager` 依赖顺序

### 8. 可测试性与可维护性
- 依赖经注入/抽象便于 mock，全局状态（`@cage`/`WorkerRegistry`/`config_params`）是否有测试隔离方案
- 方法长度（≤60 行）、圈复杂度是否可控，有无巨类
- 是否存在循环依赖（包间 import）
- 变更是否可被单目标 pytest 覆盖（见 unit-tester）

## 执行流程

### Step 1: 获取变更范围
```bash
git diff main...HEAD --name-only   # 分支差异
git diff HEAD --name-only          # 未提交变更
```

### Step 2: 按路径分类分析
| 变更路径 | 重点审核维度 |
|----------|-------------|
| `zoo_framework/core/**` | 1, 2, 3, 4, 7, 8 |
| `zoo_framework/workers/**` | 1, 3, 4, 8 |
| `zoo_framework/event/**`、`fifo/**`、`reactor/**` | 1, 4, 6, 8 |
| `zoo_framework/statemachine/**`、`core/persistence_scheduler.py` | 1, 6, 7 |
| `zoo_framework/core/waiter/**`（调度） | 3, 4, 5, 8 |
| `zoo_framework/params/**` | 1, 5, 7 |
| `zoo_framework/utils/**`、`lock/**` | 4, 6, 8 |
| `bench/**` | 4, 5 |
| `pyproject.toml`、`requirements*.txt`、`uv.lock` | 5 |
| `tests/**` | 8 |

### Step 3: 输出架构审查结论

```
## 架构审查报告
### 包结构与分层  ✅ / ⚠️ ...
### 依赖方向与单例注册  ✅ / ⚠️ ...
### 设计模式与 SOLID  ✅ / ⚠️ ...
### Python 并发最佳实践  ✅ / ⚠️ ...
### 技术选型  ✅ / ⚠️ ...
### 数据访问与持久化  ✅ / ⚠️ ...
### 横切关注点  ✅ / ⚠️ ...
### 可测试性与可维护性  ✅ / ⚠️ ...
### 架构风险项
| 风险等级 | 文件:行号 | 问题描述 | 建议方案 |
### 结论
✅ 架构审核通过 / ⚠️ 存在 N 项建议 / ❌ 存在 M 项阻断
```

## 与相关 skill 的分工

| skill | 分工 |
|-------|------|
| `architecture-principles` | 本 skill 的审查底线：硬性约束（整洁架构分层/适配器隔离/重构纪律/代码质量/渐进改造/开闭原则）逐项校验，发现违规按输出规则告警 |
| `architecture-reasoning` | 前瞻推演（长期影响 + 短期需求变化可能性），本 skill 只审现状；架构变更审查前先核查推演记录是否存在 |
| `architect-memory` | 审查产生决策后，转交 architect 追加 ADR 记录 |

## 工作约束

- 审查时不修改代码，只输出架构审查报告和建议
- 每个发现必须标注：`文件:行号` + 审核维度 + 风险等级 + 建议方案
- 不确定的技术判断标记"需人工确认"
- 审查聚焦于 diff 中的新增/修改代码，不要求重构现有代码
- 发现架构决策/技术选型结论时，转交 architect 按 architect-memory 记录 ADR
