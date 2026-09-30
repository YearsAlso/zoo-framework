---
name: python-syntax-review
description: Python（含 Rust 探针）语法审查与编码约束 Skill — 定义 Zoo Framework 项目的编码规范（架构分层/命名/类型/并发/异常/配置参数/可测试性/Rust-PyO3），供 reviewer 审查 .py 与 .rs 变更，同时作为 software-engineer 编写代码时必须遵循的编码约束；唯一事实源
---

# Python Syntax Review — Python/Rust 编码规范与审查

本 skill 是 Zoo Framework 项目代码的编码规范**唯一事实源**（Python 为主，`bench/pyo3_probe/` 及经 ADR 批准的 Rust 为辅）。**双用途**：
- **编码约束**：software-engineer 编写/修改代码时必须遵循本规范
- **审查维度**：reviewer 审查 `**/*.py` / `**/*.rs` 变更时按本规范逐维度核查

## 审查维度

### 1. 架构分层与依赖方向
- 包分层：`core/`（master、worker_registry、params_factory、waiter/、aop/）为内核；`workers/`、`event/`、`fifo/`、`reactor/`、`statemachine/`、`params/`、`utils/` 按关注点分包
- 内核禁止依赖上层业务 Worker 实现细节；稳定层（`utils/`、`constant/`）禁止反向依赖易变层
- 外部依赖（第三方库/存储/网络）经适配器隔离，业务代码不绑定外部技术类型
- 违反判断：`core` 出现对具体 Worker/业务包的直接耦合、稳定层反向 import → 🔴 阻断

### 2. 命名规范
- 模块/函数/变量 `snake_case`；类 `PascalCase`；常量 `UPPER_SNAKE`
- 私有成员/属性前导 `_`（`_execute`、`_channel_map`）；魔术方法遵循 dunder 约定
- 测试类 `Test*`、测试函数 `test_*`（与 `pyproject.toml` pytest 约定一致）
- 命名自解释，禁止单字母含义不明的公开标识符（局部短循环变量除外）

### 3. 类型注解规范
- 公开 API（模块级函数、类的公开方法、`__init__` 参数）必须有类型注解
- 用现代联合语法 `X | None`（项目要求 Python 3.13+），不再用 `Optional[X]`/`Union[...]`
- mypy 现状 `continue-on-error`，但**新增代码不得引入新的 mypy 错误**（establish-type-gate 变更目标是逐步收紧）
- 容器/映射尽量给参数化类型（`dict[str, int]`），避免裸 `dict`/`list`

### 4. 并发与异步规范
- 三条路径分清不混用：`threading`（worker 线程/`zoo_thread`）、`asyncio`（`Master.run` 的 `perform()` 循环）、`gevent`（事件管道 spawn/joinall，属待优化项）
- 阻塞调用不得跑进 asyncio 事件循环；线程要么 daemon 化要么显式 join，禁止产生游离线程
- **陷阱**：`BaseWorker.is_loop` 定义为方法但被当属性读（`if worker.is_loop:` 恒真），子类需用实例属性覆写——新增循环型 Worker 必须显式设 `is_loop` 为实例属性
- 禁止新增模块级可变全局；`@cage` 单例的类属性（`reactor_map`、`_channel_map`）已进程共享，改动须考虑测试隔离

### 5. 异常处理规范
- 禁止空 `catch`：`except Exception: pass` 必须记录或重抛（ruff 虽忽略裸 `E722`，审查仍按违规处理）
- 错误日志必须携带上下文（topic / worker 名 / 关键参数），便于并发调试
- 启动期配置缺失、存档损坏（校验和不符）fail-fast，不延迟到运行中静默降级
- 领域异常在合适的层抛出/捕获，不跨层泄漏原始异常细节

### 6. 配置与参数规范
- 新配置键必须走 `ParamsPath(value, default, aliases)`；`_resolve` 用 `is not None` 判定，**falsy 值（`False`/`0`/`""`）是有效配置值**，不得当缺失处理
- `aliases` 用于吸收历史键名（如 `worker:pool:enable` vs 旧的 `worker:pool:enabled`），避免设置被静默忽略
- params 解析发生在对应 params 模块**首次导入时**、按 `cls.__name__` 缓存——`zoo_framework/params` 必须惰性导入（在 `ParamsFactory` 读 config.json 之后），禁止在 Master 构造前 import params 类
- 同名 params 类会碰撞（键只按类名）——新增 params 类不得与既有类同名

### 7. 可测试性规范
- 依赖通过构造函数注入，避免在方法内 `new`/直接实例化外部依赖
- 避免过度使用模块级单例/静态状态阻碍测试；涉及 `@cage`/`WorkerRegistry`/`config_params` 的用例必须重置（见 assertion-integrity 规则）
- 长方法（>60 行）、巨类（>400 行）标记为可测试性/可维护性风险

### 8. Rust 探针规范（bench/pyo3_probe/ 及经 ADR 批准的 Rust）
- PyO3 0.23 约定：`#[pyfunction]`/`#[pyclass]`、`cdylib` crate 类型
- GIL 规则：不长持 `Python::with_gil`；跨界每次往返有成本（实测约 28.9 ns，回调需再跨界须计入）
- 错误用 `PyResult` + `PyErr` 返回给 Python，**不外泄 panic**（`catch_unwind` 或提前返回 Result）
- 门禁：`cargo clippy -- -D warnings` 通过；`cargo test` 覆盖探针逻辑
- 引入 Rust 到产品代码前必须回应 `bench/DECISION.md` 的 no-go 结论与再评估条件（见 architect/architecture-principles）

## 编码约束（software-engineer 使用）

编写代码时逐条遵循上述维度规范，编码完成后按序自检：命名 → 类型 → 并发 → 异常 → 配置 → 分层 → 注释（见 doc-comment）→ 架构原则（见 architecture-principles）。

## 审查流程（reviewer 使用）

### Step 1: 获取变更范围
```bash
git diff main...HEAD
```
若 diff 为空或含未提交变更，同时获取 `git diff HEAD`。

### Step 2: 逐文件分类审查
| 文件路径 | 适用维度 |
|----------|----------|
| `zoo_framework/core/**` | 1, 2, 3, 4, 5, 7 |
| `zoo_framework/workers/**` | 1, 2, 3, 4, 5, 7 |
| `zoo_framework/event/**`、`reactor/**`、`fifo/**` | 1, 2, 3, 4, 5, 7 |
| `zoo_framework/statemachine/**` | 1, 2, 3, 5, 7（持久化另见 persistence-review） |
| `zoo_framework/params/**`、`core/params_*.py` | 2, 3, 6 |
| `zoo_framework/utils/**`、`conf/**`、`constant/**` | 1, 2, 3, 5 |
| `zoo_framework/__main__.py`（CLI） | 2, 3, 5 |
| `bench/pyo3_probe/**/*.rs` | 8 |
| `tests/**` | 2, 7（断言有效性见 assertion-integrity 规则） |

### Step 3: 机械自查辅助（工具门禁）
```bash
uv run ruff check {文件} --fix        # 命名/风格/isort/pydocstyle 机械项
uv run ruff format --check {文件}     # 格式
uv run mypy {文件}                    # 类型（关注新增错误）
```
工具发现为机械线索，**架构分层/并发语义/配置时序等仍需人工深审**（不可委托工具）。

### Step 4: 输出审查结论
按严重级别输出，每条发现标注 `文件:行号` + 违反维度 + 修复方案：
- 🔴 阻断：运行时缺陷、并发/持久化不变量破坏、架构分层违规 → 必须修复
- 🟡 警告：命名/类型/异常/配置规范违反 → 建议修复
- 🔵 建议：可改进的设计模式、可测试性优化 → 可选
- ✅ 通过：符合规范
- 全部通过 → 输出：【代码审查通过】本次变更代码符合项目规范，无潜在问题

## 工作约束

- 只审查 diff 中新增/修改的代码，不要求批量重命名/重构现有代码
- 审查时不修改源码，只输出审查报告
- 每个发现必须标注：`文件:行号` + 违反的具体规范条款 + 修复代码示例
