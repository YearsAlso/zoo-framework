---
name: test-design
description: 测试用例设计 Skill — 在编码执行前针对变更模块设计测试用例清单（方法命名、边界条件、异常路径、unittest.mock/fixture 隔离方案），供 unit-tester 调用，实现测试先行（TDD）；编码后按清单编写并运行测试
---

# Test Design — 测试用例设计

在**编码执行之前**针对本次变更的模块设计测试用例清单，实现测试先行（TDD）。unit-tester 在编码阶段（leader 编排触发）调用本 skill，输出用例设计供 software-engineer 编码参考、供编码后测试执行。

## 设计流程

### Step 1: 定位变更模块与对应测试文件

| 修改的文件 | 对应测试文件 | 测试方式 |
|-----------|-------------|---------|
| `zoo_framework/workers/*` | `tests/test_worker.py`、`test_worker_registry.py`、`test_worker_scheduling.py` | 单测 |
| `zoo_framework/core/waiter/**`、调度模型 | `tests/test_scheduler_model.py`、`test_zoo_framework.py` | 单测/行为 |
| `zoo_framework/event/**`、`reactor/**` | `tests/test_event.py`、`tests/test_reactor.py` | 单测 |
| `zoo_framework/fifo/**` | `tests/test_fifo.py`、`tests/test_base_fifo.py` | 单测 |
| `zoo_framework/statemachine/**` | `tests/test_state_machine.py`、`tests/test_statemachine.py` | 单测 |
| `zoo_framework/core/persistence_scheduler.py` | `tests/test_persistence_scheduler.py` | 单测 |
| `zoo_framework/params/**` | `tests/test_config_resolution.py` | 单测 |
| `zoo_framework/utils/**` | `tests/test_utils.py`、`test_utils_extended.py` | 单测 |
| `zoo_framework/core/aop/**` | `tests/test_aop.py` | 单测 |

若对应测试文件不存在，标注"⚠️ 需新建测试文件 test_{module}.py"，由后续编码流程决定是否创建。

### Step 2: 阅读变更代码，提取可测行为
- 读取变更文件的公开方法签名、业务分支、状态流转、并发语义
- 标记需要 mock 的依赖（外部库/存储/时间）
- 标记输入约束（类型/边界/空值）与异常路径
- 标记涉及的全局状态（`@cage`/`WorkerRegistry`/`config_params`）→ 设计重置策略

### Step 3: 输出测试用例清单

```
## 测试用例设计（{module}）

### 用例清单
| # | 测试方法名 | 场景 | 输入 | 预期结果 |
|---|-----------|------|------|---------|
| 1 | {method}_{scenario}_{expected} | 正常路径 | ... | ... |
| 2 | {method}_{scenario}_{expected} | 边界条件 | ... | ... |
| 3 | {method}_{scenario}_{expected} | 异常路径 | ... | ... |

### 依赖隔离（unittest.mock / fixture）
- patch：{目标}（{用途}）
- fixture：{名称}（重置 {全局状态}）

### 覆盖检查
- [ ] 正常路径（Happy Path）
- [ ] 边界条件（空值/falsy 配置值/临界值）
- [ ] 异常路径（非法输入/存档损坏/依赖抛错）
- [ ] 并发/状态流转守卫（is_loop、超时、重试，如适用）
- [ ] 全局状态已隔离（cage/registry/config 重置）
```

## 用例设计规范

### 测试方法命名
`{method}_{scenario}_{expected}`（snake_case，与 pytest 约定一致），如：
- `test_get_by_topic_unregistered_returns_none`
- `test_execute_error_rate_high_flips_status_to_warning`
- `test_save_state_uses_atomic_replace`

### 必覆盖场景
1. **正常路径**：合法输入 → 预期成功结果
2. **边界条件**：空值、falsy 配置值（`False`/`0`/`""`）、临界值、超时边界
3. **异常路径**：非法输入、目标不存在、存档校验失败、依赖抛错
4. **状态/并发守卫**：循环语义、重试、状态机前置条件（如适用）

### 约束
- 每个测试方法必须有**有牙齿的**断言 —— 判据：**若把实现改错，这条断言会红吗？** 不会则无效（详见 `.claude/rules/assertion-integrity.md`）
- **禁止对可变对象使用引用捕获断言**（`assert_called_with(可变对象)` / 验证期读 `obj.可变字段`）：本框架普遍就地改写对象（`node.retry_count += 1`、`worker.status = ...`），而 mock 在验证期读的是**最终态** ⇒ 断言恒真。**一律改用 `side_effect` 调用时快照**（记录每次调用的字段值，再对整条序列断言）
- 否定式断言前先证明集合非空（`assert writes`），否则对空集合恒真
- 涉及 `@cage`/`WorkerRegistry`/`config_params` 的用例必须重置（进程级状态泄漏会让断言在错误实现下依旧绿）
- 使用 `unittest.mock` / pytest fixture 隔离外部依赖（时间、文件、网络、线程）
- 单次设计 ≤30s，只输出用例清单**不写测试文件**（编码后由 unit-tester 编写执行）

## 输出形式（编码前场景）

- 变更仅涉及注释/配置/文档 → 输出"✅ 无新测试需求，跳过测试设计"
- 变更涉及业务逻辑 → 输出完整用例清单
- 对应测试文件不存在 → 标注"⚠️ 需新建测试文件 test_{module}.py"，由后续编码流程决定是否创建

## 工作约束

- 本 skill 只做**用例设计**，不编写测试代码（编写由 unit-tester 编码后执行）
- 设计基于变更代码的实际行为，不脑补未实现的功能
- 不确定的预期行为标注"需确认"
