# 🎪 Zoo Framework 开发文档

> Zoo Framework 是一个**后台任务编排框架**：调度 Worker、投递事件、持久化状态，
> 嵌入服务进程内运行长期存活的后台任务。
>
> 并发模型：**多线程**已实现（`thread` / `thread_pool` 两种调度模式）；**协程**由
> `AsyncWorker` 承载，在调度路径上执行；**多进程未实现**（模式常量是占位，请求会被
> 显式拒绝）。
>
> 框架用动物园隐喻命名（Worker / Cage / Master / Event / FIFO），但**隐喻只影响命名，
> 不影响语义**。各名称对应的实际组件见下方「核心概念」。

---

## 📚 文档导航

| 文档 | 说明 | 目标读者 |
|------|------|----------|
| [📖 架构设计](ARCHITECTURE.md) | 框架整体架构、核心概念 | 所有开发者 |
| [🚀 快速开始](DEVELOPMENT.md) | 开发环境搭建、运行项目 | 新加入开发者 |
| [📝 贡献指南](CONTRIBUTING.md) | 代码规范、提交规范 | 贡献者 |
| [🐛 调试指南](DEBUGGING.md) | 常见问题排查、调试技巧 | 开发者 |
| [📊 API 参考](API_REFERENCE.md) | 核心 API 文档 | 开发者 |

---

## 🎯 项目概览

### 核心概念

```mermaid
graph TB
    subgraph 🎪 Zoo Framework
        M[👨‍🌾 Master 园长] -->|管理| W[🦁 Worker 动物]
        M -->|管理| C[🏠 Cage 笼子<br/>= ScopedContainer]
        M -->|管理| F[🥘 FIFO 饲养员队列]
        W -->|住在| C
        W -->|监听| E[🍎 Event 食物]
        E -->|排队| F
    end
```

### 技术栈

- **Python**: 3.13+
- **异步支持**: asyncio；事件投递与状态 effect 基于线程执行器（concurrent.futures，
  gevent 已随 `align-execution-primitives` 移除）
- **代码质量**: Ruff, MyPy, pre-commit
- **测试**: pytest, pytest-cov, pytest-asyncio
- **CI/CD**: GitHub Actions

---

## 🚀 5 分钟快速开始

### 1. 克隆项目

```bash
git clone https://github.com/YearsAlso/zoo-framework.git
cd zoo-framework
```

### 2. 安装依赖

```bash
# 创建虚拟环境（请使用 3.13；仓库默认的 `python` 可能指向一个 3.9 环境，
# 它无法导入本包）
python3.13 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或: .venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"
```

### 3. 安装 pre-commit hooks

```bash
pre-commit install
```

### 4. 运行测试

```bash
pytest
```

### 5. 运行示例

```bash
python example/threads/demo_thread.py
```

---

## 📁 项目结构

```
zoo-framework/
├── zoo_framework/          # 核心源码
│   ├── core/              # 核心模块
│   │   ├── master.py      # 👨‍🌾 园长（Master）
│   │   ├── waiter/        # 🍽️ 饲养员（Waiter）
│   │   ├── persistence_scheduler.py  # 💾 持久化调度器
│   │   └── worker_registry.py        # 📝 Worker 注册表
│   ├── workers/           # 👷 Worker 实现
│   │   ├── base_worker.py # 基础 Worker
│   │   ├── event_worker.py
│   │   ├── state_machine_work.py
│   │   └── async_worker.py           # 🔄 异步 Worker
│   ├── statemachine/      # 🔄 状态机
│   │   ├── state_machine_manager.py
│   │   ├── state_scope.py
│   │   └── state_index_factory.py    # 🏭 索引工厂
│   ├── fifo/              # 📊 FIFO 队列
│   ├── reactor/           # 📢 事件响应器
│   │   ├── event_reactor_req.py      # 带通道隔离
│   │   └── event_reactor_manager.py
│   ├── plugin/            # 🔌 Plugin 系统
│   │   └── __init__.py    # PluginManager
│   └── utils/             # 🛠️ 工具类
│       ├── structured_log.py         # 📝 结构化日志
│       └── ...
├── tests/                 # 🧪 测试
├── example/               # 📚 示例代码
├── docs/                  # 📖 文档
├── pyproject.toml         # 📦 项目配置
└── requirements-dev.txt   # 🛠️ 开发依赖
```

---

## 🔑 核心模块详解

### 👨‍🌾 Master - 园长

Master 是框架的入口，负责管理所有 Worker 的生命周期。

```python
from zoo_framework.core import Master

# 创建 Master（自动注册并实例化内置的系统 Worker）
master = Master()

# 注册自定义 Worker —— 注册后才进入调度
master.register_worker("MyWorker", MyWorker)

# 运行（阻塞，Ctrl-C 退出）
master.run()

# 获取健康报告（⚠️ 指标链路尚未接通，execute_count 恒为 0）
report = master.get_health_report()

# 停机：停止派发 → 取消调度任务 → 停事件循环 → 停监控 → 注销 Worker
master.shutdown()
```

### 👷 Worker - 动物

Worker 是执行业务逻辑的基本单元。

```python
from zoo_framework.workers import BaseWorker


class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            {
                "is_loop": True,  # 循环执行（属性，读取时不要加括号）
                "delay_time": 1.0,  # 单次执行结束后的等待秒数
                "name": "MyWorker",
                # "run_timeout": 30,  # 可选：执行超时（观测 + 熔断，不强制终止）
            }
        )

    def _execute(self):
        print("执行业务逻辑")
```

可用钩子（都是可选的，覆写即可）：`_execute`（必须）、`_destroy(result)`
（注销时调用，停机流程会触发）、`_on_error`、`_on_done`。

### 🏠 Cage - 笼子

笼子对应 **`ScopedContainer`**：按**作用域**持有共享实例的容器。

作用域有三种，解析时以**显式句柄**传入（没有"不传即进程级"的默认值——那会静默破坏会话隔离）：

| 作用域 | 含义 |
|---|---|
| `ScopeKind.PROCESS` | 全进程唯一，跨会话同一实例 |
| `ScopeKind.SESSION` | 每个会话一个（会话边界由 `RunIdentity.session_id` 承载） |
| `ScopeKind.PROTOTYPE` | 每次解析都新建，不缓存 |

```python
from zoo_framework.core.container import Scope, ScopeKind, ScopedContainer, ThreadSafety

container = ScopedContainer()
container.register(
    MyService, scope_kind=ScopeKind.PROCESS, thread_safety=ThreadSafety.INSTANCE_GUARANTEED
)  # 必填，无隐式默认
service = container.resolve(MyService, Scope.process())
```

容器的语义边界值得先记住四条：**解析以作用域为界**（同作用域内同一注册项得到同一实例，
不同会话作用域得到不同实例）；**注册项标识是模块 + 限定名**（不是裸类名，故同名但定义位置
不同的类不会串号）；**解析保留类型契约**（`isinstance` / `issubclass` 照常可用——它不替换类）；
**线程安全归属必须显式声明**（`INSTANCE_GUARANTEED` / `CONTAINER_SERIALIZED` / `SINGLE_THREAD`，
未声明即拒绝注册，因为隐式默认一个安全假设正是缺陷的温床）。

生命期由 `release(scope)` 显式结束（幂等，对每个实例只触发一次声明的销毁钩子），测试可用
`replace(target, scope, ...)` 注入假实现、用 `reset()` 回到初始状态。

> ⚠️ **`@cage` 装饰器已删除**（不再从 `zoo_framework.core.aop` / `zoo_framework.core` 导出）。
> 它过去用"把类替换成工厂函数"提供单例，后果是 `issubclass` / `isinstance` 双双失效，且两个
> 同名类会按裸类名互相覆盖。框架内部的进程级共享现由容器承担（`process_scoped` 装饰器，
> **不**替换类）。

> ⚠️ **Worker 必须以类的形式注册**：`WorkerRegistry` 用 `issubclass` 校验契约，传入函数或实例
> 会抛 `TypeError: issubclass() arg 1 must be a class`。这条约束与 `@cage` 无关，删除它之后
> 依然成立。

---

## 🛠️ 开发工具

### 代码质量检查

```bash
# Ruff 代码检查
ruff check zoo_framework

# Ruff 自动修复
ruff check zoo_framework --fix

# Ruff 格式化
ruff format zoo_framework

# MyPy 类型检查
mypy zoo_framework
```

### 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_worker.py

# 带覆盖率
pytest --cov=zoo_framework --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html
```

### 安全扫描

```bash
# Bandit 安全扫描
bandit -r zoo_framework
```

---

## 📦 依赖管理

### 生产依赖

```toml
[project.dependencies]
click>=8.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
typing-extensions>=4.7.0
```

### 开发依赖

```bash
pip install -e ".[dev]"
```

包含：Ruff, MyPy, pytest, pre-commit, bandit 等

---

## 🔧 配置说明

### pyproject.toml 关键配置

```toml
[project]
name = "zoo-framework"
version = "0.8.0"
requires-python = ">=3.13"

[project.optional-dependencies]
dev = ["ruff", "mypy", "pytest", ...]
docs = ["mkdocs", ...]

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.mypy]
python_version = "3.13"
```

---

## 🌟 特性清单

### P0 - 必须修复 ✅

- [x] Plugin 系统实现
- [x] Worker 延迟管理
- [x] 线程安全修复
- [x] 内存泄漏修复

### P1 - 重要功能 ✅

- [x] SVM Worker 状态向量机
- [x] 持久化逻辑解耦
- [x] 文件校验和备份
- [x] 事件通道隔离

### P2 - 优化项 ✅

- [x] 优先级算法优化
- [x] Master 参数优化
- [x] Worker 注册机制重构
- [x] 状态机索引工厂模式

### 8 个优化方案 ✅

- [x] 现代打包工具 (pyproject.toml)
- [x] 代码质量工具 (Ruff/MyPy)
- [x] 测试覆盖
- [x] CI/CD 增强
- [x] Worker 注册重构
- [x] Plugin 系统
- [x] 结构化日志
- [x] 异步 IO 优化

---

## 📞 获取帮助

- 📖 [完整文档](https://yearsalso.github.io/zoo-framework/)
- 🐛 [Issue Tracker](https://github.com/YearsAlso/zoo-framework/issues)
- 💬 [Discussions](https://github.com/YearsAlso/zoo-framework/discussions)

---

## 📄 许可证

Apache License 2.0 © XiangMeng
