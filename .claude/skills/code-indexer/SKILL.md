---
name: code-indexer
description: 代码索引导航 Skill — Grep/Glob 动态定位；根据业务需求快速定位代码位置，建立 需求→配置→装饰器→Worker/Reactor→FIFO/调度器→持久化 的全链路映射；供 architect 推演前、software-engineer 编码前与 reviewer 审查前引入
---

# Code Indexer Skill — 代码索引导航

给定一个业务需求或关键词，快速定位对应的代码文件、类、方法、配置键、装饰器。**只做索引查询和路径导航，不修改任何代码。**

## 使用场景

- **architect**：架构推演（architecture-reasoning）与设计前引入，快速确认变更涉及的代码现状与影响面
- **software-engineer**：编码实现前引入，定位需求对应的配置/装饰器/Worker/Reactor/FIFO/持久化落点，确保修改落点准确
- **reviewer**（可选）：审查前引入，定位变更范围与全链路影响

## 项目结构速查

```
zoo_framework/
├── core/            # master.py, worker_registry.py, params_factory.py, params_path.py,
│                    # persistence_scheduler.py, zoo_thread.py, aop/（装饰器）, waiter/（调度）
├── workers/         # base_worker, event_worker, state_machine_work, async_worker, worker_*值对象
├── event/           # 事件通道：channel manager / register / provider / fifo 入口
├── fifo/            # base_fifo / delay_fifo / event_fifo / single_fifo 队列
├── reactor/         # event_reactor_manager / priority / retry / waiter_result_reactor
├── statemachine/    # StateMachineManager / StateScope / StateIndex / state_node / effect
├── params/          # worker_params / event_params / log_params / state_machine_params
├── lock/            # base_lock / count_lock / time_lock
├── utils/           # thread_safe_dict / cmd / datetime / file / log / structured_log / ws
├── conf/ constant/ templates/ plugin/
tests/               # pytest 套件（test_*.py）
bench/               # 性能测量区（非产品代码），pyo3_probe/ 为 Rust 探针
openspec/            # specs/<capability>/spec.md（行为规格）、changes/<id>/（在途变更）
```

## 链路映射模型（本项目）

需求不经过 HTTP API，而经**配置 + 装饰器**驱动。定位链路：

```
需求 → 配置键（config.json / params 类 / ParamsPath）
     → 装饰器（@worker / @event / @cage / @params）
     → Worker 或 Reactor（执行体）
     → FIFO / 调度器（EventChannel、waiter、SchedulerModel）
     → 持久化（statemachine 存档、PersistenceScheduler）
```

## 查询方法（Grep/Glob 动态定位）

### 模式 1：需求 → 配置键
```bash
# 找配置键定义（ParamsPath）与其归属 params 类
grep -rn "ParamsPath(" zoo_framework/params/ zoo_framework/core/params_path.py
# 找 _exports / config.json 引用
grep -rn "_exports\|config_path\|config.json" zoo_framework/core/params_factory.py
```

### 模式 2：需求 → 装饰器落点
```bash
grep -rn "@worker\|@event\|@cage\|@params" zoo_framework/ --include="*.py"
# 装饰器定义本体
grep -rn "def worker\|def event\|def cage\|def params" zoo_framework/core/aop/
```

### 模式 3：需求 → Worker / Reactor 执行体
```bash
grep -rn "class .*Worker" zoo_framework/workers/
grep -rn "def _execute" zoo_framework/workers/            # 执行体
grep -rn "def perform\|def execute" zoo_framework/reactor/ # reactor 分发
```

### 模式 4：需求 → 事件通道 / FIFO
```bash
grep -rn "class Event.*Manager\|EventChannel\|refresh_channel" zoo_framework/event/
grep -rn "class .*FIFO\|EventNode\|response_mechanism" zoo_framework/fifo/ zoo_framework/event/
```

### 模式 5：需求 → 状态机 / 持久化
```bash
grep -rn "class State.*\|StateIndex\|StateScope" zoo_framework/statemachine/
grep -rn "pickle\|PersistenceStrategy\|os.replace\|checksum" zoo_framework/core/persistence_scheduler.py zoo_framework/statemachine/
```

### 模式 6：需求 → 调度模型
```bash
grep -rn "SchedulerModel\|ThreadPerTask\|ThreadPool\|WorkerDispatchCore\|execute_service" zoo_framework/core/waiter/
```

### 模式 7：需求 → 规格文档
```bash
# 定位某能力对应的 openspec 规格
ls openspec/specs/
grep -rn "SHALL\|MUST" openspec/specs/{capability}/spec.md
```

### 模式 8：全链路追踪
从需求关键词出发，按"配置键 → 装饰器注册 → 执行体 → 通道/调度 → 持久化"逐跳 grep 串联，**必须保留多步 Grep 串联**验证，每一步给出 `文件:行号`。

## 输出格式

```
## 代码索引结果

### 需求：{用户需求}

### 链路
- 配置：`{params 类}:{行号}`（键 `{a:b:c}`）
- 装饰器注册：`{文件}:{行号}`（@worker/@event/@cage）
- 执行体：`{Worker/Reactor 类}.{方法}` → `文件:行号`
- 通道/调度：`EventChannel/SchedulerModel` → `文件:行号`
- 持久化：`文件:行号`（如适用）

### 关键文件
| 层 | 文件 | 行号 |
|----|------|------|
| 配置参数 | zoo_framework/params/*.py | :N |
| 装饰器 | zoo_framework/core/aop/*.py | :N |
| Worker | zoo_framework/workers/*.py | :N |
| 事件/FIFO | zoo_framework/event|fifo/*.py | :N |
| 状态机/持久化 | zoo_framework/statemachine/*.py, core/persistence_scheduler.py | :N |

### 影响范围
- 涉及配置键：N 个
- 涉及装饰器/Worker/Reactor：N 个
- 涉及持久化/调度：N 处
```

## 工作约束
- 不修改任何代码，只做索引查询和路径导航
- 用 Grep/Glob 动态定位，**不依赖记忆或硬编码映射**
- 每次查询给出 `文件:行号` 级别的精确定位
- 需要时给出全链路追踪（从配置/装饰器入口到持久化）
