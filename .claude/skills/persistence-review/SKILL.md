---
name: persistence-review
description: 持久化与状态存档审查 Skill — 审查 pickle 存档路径的原子写（.tmp + os.replace）、校验和、滚动备份（backups/ ≤5）、加载兼容性与安全，对应 openspec state-machine 与 worker-lifecycle 规格；供 reviewer 在 statemachine/、persistence_scheduler.py 变更时调用
---

# Persistence Review — 持久化与状态存档审查

审查状态机/持久化相关变更是否保持"写入不损坏、加载可校验、备份不丢失、格式可兼容"的不变量。对应 `openspec/specs/state-machine/spec.md` 与 `openspec/specs/worker-lifecycle/spec.md`，实现落在 `zoo_framework/core/persistence_scheduler.py`（`PersistenceScheduler`/`PicklePersistenceStrategy`）与 `zoo_framework/statemachine/**`。reviewer 在 `statemachine/**`、`persistence_scheduler.py` 变更时调用本 skill。

## 触发变更路径
- `zoo_framework/core/persistence_scheduler.py`（原子写/校验/备份/恢复）
- `zoo_framework/statemachine/**`（`StateMachineManager`/`StateScope`/`StateIndex`/`StateMachineWorker`）
- 存档配置键 `stateMachine:picklePath` 相关解析（`params/state_machine_params.py`）

## 审查维度

### 1. 原子写（不可损坏）
- 写入 MUST 先写 `.tmp` 再 `os.replace`（同目录同卷），禁止直接原地覆写存档文件（崩溃会留下半写文件）
- 违反判断：`open(path, 'wb')` 直接写目标、无 tmp+replace、tmp 与目标不同目录 → 🔴

### 2. 校验和（可检测损坏）
- 存档 MUST 带校验和；加载时校验失败 MUST 拒绝加载并告警/回退，不得静默使用损坏数据
- 校验和覆盖范围是否完整（含数据体，不含自身）
- 违反判断：加载不校验、校验失败仍继续、校验范围遗漏 → 🔴

### 3. 滚动备份（可恢复）
- 备份 MUST 保留至 5 份于同级 `backups/` 目录；超出按时间序滚动淘汰最旧
- 备份命名唯一且字典序==时间序（详见 cross-platform-io 备份命名条款）
- 淘汰/保留逻辑不得误删最新有效备份
- 违反判断：备份数量无上限/无下限、命名可覆盖、误删最新 → 🟡/🔴

### 4. 加载兼容性（跨版本）
- pickle 反序列化对**类名/模块路径/字段**敏感：重命名 `zoo_framework` 内的可序列化类或移动模块而不提供迁移说明 → 🔴（旧存档加载会失败或错解）
- 存档格式变更 MUST 有兼容策略（版本标记 / 迁移 / 明确"旧存档作废"公告），禁止无声破坏
- 违反判断：改了可序列化类的 `__qualname__`/模块路径却无迁移 → 🔴

### 5. 反序列化安全
- pickle 加载仅对**受信来源**（见 security-review 维度 1）；存档路径来自配置时校验合法、防目录穿越
- 理想用受限 `Unpickler` 白名单可控类型面

### 6. 状态机运行语义
- `StateMachineWorker`（loop，5s）首 pass 加载、后续 pass 保存的时序是否正确（勿在加载前覆写）
- `StateIndex` 后端（默认 `ThreadSafeDict`）并发安全；`@cage`/进程级状态在测试中的重置
- 持久化失败不得静默丢状态——必须记录带上下文的错误（对齐 Worker 错误率告警机制）

## 执行流程

### Step 1: 获取变更范围并定位
```bash
git diff main...HEAD --name-only
```
命中触发路径 → 用 code-indexer 定位存档写/读/备份调用链。

### Step 2: 逐维度核查
按 1-6 维度检查，每条发现给 `文件:行号` + 违反的不变量/openspec 条款 + 修复建议。

### Step 3: 输出报告
```
## 持久化审查报告
### 原子写：✅ / 🔴 ...
### 校验和：✅ / 🔴 ...
### 滚动备份：✅ / 🟡 ...
### 加载兼容性：✅ / 🔴 ...
### 反序列化安全：✅ / 🔴 ...
### 状态机运行语义：✅ ...
### 结论：✅ 通过 / ⚠️ 建议 / ❌ 阻断
```

## 与相关 skill 的分工
| skill | 分工 |
|-------|------|
| `security-review` | 管 pickle 反序列化的**信任边界/代码执行风险**；本 skill 管**数据完整性/兼容性不变量** |
| `cross-platform-review` | 管 `os.replace` 跨卷原子性与备份命名的**平台差异**；本 skill 管备份策略本身的正确性 |
| `assertion-integrity` | 持久化测试断言须"有牙齿"（注入损坏存档确认断言变红） |

## 工作约束
- 只审查不修改代码，只输出报告
- 每个发现标注 `文件:行号` + 违反的持久化不变量/openspec 条款 + 修复建议
- 触及"存档损坏不可静默、跨版本不可无声破坏"的项一律 🔴
- 不确定的兼容性判断标记"需人工确认"，建议补加载兼容性回归测试
