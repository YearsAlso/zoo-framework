# Zoo Framework 优化方案

> 分支: feat-xmeng  
> 生成日期: 2026-02-12  
> 版本: v1.0

---

## 📋 未完成内容汇总

### 1. Plugin 系统 (优先级: P0)

**位置**: `zoo_framework/plugin/__init__.py`

**现状**: 目录为空，仅有 TODO 注释

**未完成内容**:
- [ ] 设计并实现插件系统架构
- [ ] 提供插件注册和加载机制
- [ ] 允许开发者通过插件实现自定义功能

**影响**: 严重限制框架的可扩展性

---

### 2. Worker 延迟时间管理 (优先级: P0)

**位置**: `zoo_framework/plugin/__init__.py`

**现状**: 延迟时间控制不够灵活

**未完成内容**:
- [ ] 设计时间对象管理器
- [ ] 使用时间管理对象控制 Worker 的延迟执行
- [ ] 支持动态调整延迟时间

**影响**: 影响任务调度的精确性和灵活性

---

### 3. SVM Worker (优先级: P1)

**位置**: 
- `zoo_framework/plugin/__init__.py`
- `zoo_framework/core/master.py:36`

**现状**: 计划中但未实现

**未完成内容**:
- [ ] 实现 SVM (State Vector Machine) Worker
- [ ] 集成 SVM Manager 到 Waiter
- [ ] 支持基于状态向量的工作器管理

**影响**: 缺少高级工作器调度能力

---

### 4. 状态机持久化优化 (优先级: P1)

**位置**: `zoo_framework/workers/state_machine_work.py`

**现状**: 持久化逻辑耦合在 Worker 中

**未完成内容**:
- [ ] 将持久化逻辑移到调度器中
- [ ] 调度器决定何时进行持久化
- [ ] 状态树按作用域划分存储
- [ ] 每个作用域对应一个文件

**影响**: 状态管理不够灵活，难以扩展

---

### 5. 线程安全问题 (优先级: P0)

**位置**: `zoo_framework/workers/state_machine_work.py`

**未完成内容**:
- [ ] 状态机加载时需要加线程锁
- [ ] 文件读写需要同步机制

**影响**: 存在并发安全风险，可能导致数据不一致

---

### 6. 文件校验与备份 (优先级: P1)

**位置**: `zoo_framework/workers/state_machine_work.py`

**未完成内容**:
- [ ] 实现文件校验机制（校验和/签名）
- [ ] 实现文件备份功能
- [ ] 实现文件切片功能（大文件分片存储）

**影响**: 数据可靠性不足，存在丢失风险

---

### 7. 事件优先级算法优化 (优先级: P2)

**位置**: `zoo_framework/fifo/node/event_fifo_node.py:62`

**现状**:
```python
def __index__(self):
    # TODO: 优先级计算公式待优化
    return self.priority + self.create_time % 100000
```

**问题**: 优先级计算过于简单，可能导致优先级反转

**建议方案**:
```python
def __index__(self):
    # 使用加权优先级算法
    time_weight = 0.3
    priority_weight = 0.7
    time_score = (time.time() - self.create_time) / 1000  # 秒级时间差
    return int(priority_weight * self.priority + time_weight * time_score)
```

---

### 8. Master 类优化 (优先级: P2)

**位置**: `zoo_framework/core/master.py`

**未完成内容**:
- [ ] 创建各类注册器（统一注册机制）
- [ ] 移除多余的 `loop_interval` 参数
- [ ] 使用纯异步方式执行
- [ ] 集成 SVM Manager

---

### 9. Worker 注册机制重构 (优先级: P2)

**位置**: 
- `zoo_framework/core/aop/worker.py`
- `zoo_framework/core/waiter/base_waiter.py`

**未完成内容**:
- [ ] 使用 Register 模式注册 Worker
- [ ] 属性和方法都通过 Register 注册
- [ ] 取消主动注入，创建注册器时自动注册

---

### 10. 事件通道隔离 (优先级: P1)

**位置**: 
- `zoo_framework/reactor/event_reactor_req.py`
- `zoo_framework/reactor/event_reactor_manager.py`

**未完成内容**:
- [ ] 事件监听指定通道
- [ ] 防止不同通道的事件被误处理

**影响**: 可能导致事件处理混乱

---

### 11. 状态机作用域优化 (优先级: P2)

**位置**: `zoo_framework/statemachine/state_scope.py`

**未完成内容**:
- [ ] 将索引创建优化为工厂模式
- [ ] 索引设置为对象，支持多种实现方式
- [ ] 实现子节点删除功能

---

### 12. 内存泄漏问题 (优先级: P0)

**位置**: `example/threads/demo_thread.py`

**问题**: FIXME 标注 - 操作状态机有内存泄漏

**需要**: 
- [ ] 调查内存泄漏原因
- [ ] 修复泄漏点
- [ ] 添加内存监控

---

## 🚀 可实施的优化方案

### 方案 1: 引入现代 Python 打包工具 (优先级: P0)

**现状问题**:
- 使用 `setup.py` (已过时)
- 缺少 `pyproject.toml`
- 依赖管理分散

**实施方案**:

1. **创建 `pyproject.toml`**:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "zoo-framework"
version = "0.2.0"
description = "A simple and quick multi-threaded framework"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "Apache-2.0" }
authors = [
    { name = "XiangMeng", email = "mengxiang931015@live.com" }
]
keywords = ["framework", "multi-threading", "state-machine", "async"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "click>=8.0.0",
    "jinja2>=3.0.0",
    "gevent>=23.0.0",
    "pyyaml>=6.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
    "mypy>=1.14.0",
    "pre-commit>=4.0.0",
]

[project.scripts]
zfc = "zoo_framework.__main__:zfc"

[tool.ruff]
target-version = "py310"
line-length = 100
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.10"
disallow_untyped_defs = true
```

**收益**:
- 标准化 Python 项目结构
- 更好的依赖管理
- 支持现代工具链 (uv, pipx)

---

### 方案 2: 添加代码质量工具 (优先级: P0)

**实施方案**:

1. **添加 `.pre-commit-config.yaml`**:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.1
    hooks:
      - id: mypy
```

2. **添加 Makefile**:
```makefile
.PHONY: lint format test install-dev

install-dev:
	pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check zoo_framework tests
	mypy zoo_framework

format:
	ruff format zoo_framework tests
	ruff check --fix zoo_framework tests

test:
	pytest tests/ -v --cov=zoo_framework --cov-report=html
```

**收益**:
- 统一代码风格
- 自动类型检查
- 防止低质量代码提交

---

### 方案 3: 完善测试覆盖 (优先级: P1)

**现状**: `test/` 目录只有基础文件

**实施方案**:

1. **单元测试结构**:
```
tests/
├── __init__.py
├── conftest.py          # 共享 fixtures
├── unit/
│   ├── __init__.py
│   ├── test_fifo.py
│   ├── test_statemachine.py
│   ├── test_workers.py
│   └── test_event.py
├── integration/
│   ├── __init__.py
│   └── test_master.py
└── fixtures/
    └── config.json
```

2. **示例测试代码**:
```python
# tests/unit/test_fifo.py
import pytest
from zoo_framework.fifo import EventFIFO
from zoo_framework.fifo.node import EventNode


class TestEventFIFO:
    def test_push_and_pop(self):
        fifo = EventFIFO()
        node = EventNode("test_topic", "test_content")
        fifo.push(node)
        
        result = fifo.pop()
        assert result.topic == "test_topic"
    
    def test_priority_ordering(self):
        fifo = EventFIFO()
        low = EventNode("low", "content", priority=1)
        high = EventNode("high", "content", priority=10)
        
        fifo.push(low)
        fifo.push(high)
        
        assert fifo.pop().topic == "high"
```

**收益**:
- 提高代码可靠性
- 便于重构和优化
- CI/CD 集成

---

### 方案 4: 增强 CI/CD 流水线 (优先级: P1)

**现状**: 只有 Pylint 检查

**建议的 `.github/workflows/ci.yml`**:
```yaml
name: CI

on:
  push:
    branches: [main, feat-xmeng]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Lint with Ruff
        run: ruff check zoo_framework tests

      - name: Type check with MyPy
        run: mypy zoo_framework

      - name: Test with pytest
        run: pytest tests/ -v --cov=zoo_framework --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

**收益**:
- 自动化质量检查
- 多版本 Python 兼容
- 覆盖率追踪

---

### 方案 5: 重构 Worker 注册机制 (优先级: P2)

**设计模式**: 注册表模式 (Registry Pattern)

**实施方案**:

1. **创建注册器基类**:
```python
# zoo_framework/core/registry.py
from typing import TypeVar, Generic, Callable, Dict

T = TypeVar('T')


class Registry(Generic[T]):
    """通用注册器"""
    
    def __init__(self):
        self._items: Dict[str, T] = {}
    
    def register(self, name: str, item: T) -> None:
        """注册项目"""
        if name in self._items:
            raise ValueError(f"{name} already registered")
        self._items[name] = item
    
    def get(self, name: str) -> T | None:
        """获取项目"""
        return self._items.get(name)
    
    def get_all(self) -> Dict[str, T]:
        """获取所有项目"""
        return self._items.copy()
    
    def unregister(self, name: str) -> None:
        """注销项目"""
        if name in self._items:
            del self._items[name]


# Worker 专用注册器
worker_registry = Registry[BaseWorker]()
```

2. **装饰器注册方式**:
```python
# zoo_framework/core/aop/worker.py
from zoo_framework.core.registry import worker_registry


def register_worker(name: str | None = None):
    """Worker 注册装饰器"""
    def decorator(cls):
        worker_name = name or cls.__name__
        instance = cls()
        worker_registry.register(worker_name, instance)
        return cls
    return decorator


# 使用示例
@register_worker("state_machine")
class StateMachineWorker(BaseWorker):
    pass
```

**收益**:
- 解耦组件依赖
- 更灵活的扩展机制
- 支持动态加载

---

### 方案 6: 实现 Plugin 系统 (优先级: P1)

**设计**: 基于入口点 (Entry Points) 的插件系统

**实施方案**:

1. **插件接口定义**:
```python
# zoo_framework/plugin/base.py
from abc import ABC, abstractmethod
from typing import Any


class Plugin(ABC):
    """插件基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass
    
    @abstractmethod
    def initialize(self, context: Any) -> None:
        """初始化插件"""
        pass
    
    @abstractmethod
    def destroy(self) -> None:
        """销毁插件"""
        pass


class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
    
    def load_plugin(self, plugin_class: type[Plugin]) -> None:
        """加载插件"""
        instance = plugin_class()
        instance.initialize(self)
        self._plugins[instance.name] = instance
    
    def load_plugins_from_entry_points(self) -> None:
        """从入口点加载插件"""
        import importlib.metadata
        
        for entry_point in importlib.metadata.entry_points(
            group="zoo_framework.plugins"
        ):
            plugin_class = entry_point.load()
            self.load_plugin(plugin_class)
```

2. **插件配置**:
```toml
# 插件的 pyproject.toml
[project.entry-points."zoo_framework.plugins"]
my_plugin = "my_plugin.plugin:MyPlugin"
```

**收益**:
- 框架可扩展性大幅提升
- 第三方开发者可轻松扩展
- 支持热插拔

---

### 方案 7: 添加结构化日志 (优先级: P2)

**现状**: 使用简单的 LogUtils

**实施方案**:

```python
# zoo_framework/utils/logger.py
import structlog
import logging


def configure_logging(debug: bool = False) -> None:
    """配置结构化日志"""
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    if debug:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str):
    """获取日志记录器"""
    return structlog.get_logger(name)
```

**收益**:
- 结构化日志便于分析
- 支持 JSON 输出（生产环境）
- 更好的调试体验

---

### 方案 8: 性能优化 - 使用异步 IO (优先级: P2)

**现状**: Master.perform() 使用 asyncio.sleep 但 Worker 是同步的

**实施方案**:

```python
# zoo_framework/core/async_worker.py
import asyncio
from abc import abstractmethod
from .base_worker import BaseWorker


class AsyncWorker(BaseWorker):
    """异步 Worker 基类"""
    
    @abstractmethod
    async def execute_async(self) -> None:
        """异步执行方法"""
        pass
    
    async def run(self) -> None:
        """运行循环"""
        while self.is_loop:
            await self.execute_async()
            if self.delay_time > 0:
                await asyncio.sleep(self.delay_time)


# zoo_framework/core/waiter/async_waiter.py
class AsyncWaiter(BaseWaiter):
    """异步 Waiter"""
    
    async def execute_service(self) -> None:
        """异步执行服务"""
        tasks = []
        for name, worker in self.workers.items():
            if isinstance(worker, AsyncWorker):
                tasks.append(worker.run())
            else:
                # 同步 Worker 在线程池中执行
                loop = asyncio.get_event_loop()
                tasks.append(
                    loop.run_in_executor(self.executor, worker.execute)
                )
        
        await asyncio.gather(*tasks, return_exceptions=True)
```

**收益**:
- 更高的并发性能
- 更好的资源利用率
- 支持异步 IO 操作

---

## 📊 优先级矩阵

| 优化项 | 优先级 | 难度 | 收益 | 建议时间 |
|--------|--------|------|------|----------|
| Plugin 系统 | P1 | 中 | 高 | 1-2 周 |
| Worker 延迟管理 | P0 | 低 | 高 | 2-3 天 |
| 线程安全修复 | P0 | 中 | 高 | 3-5 天 |
| pyproject.toml | P0 | 低 | 高 | 1 天 |
| 代码质量工具 | P0 | 低 | 中 | 1 天 |
| 测试覆盖 | P1 | 中 | 高 | 1-2 周 |
| CI/CD 增强 | P1 | 低 | 中 | 2-3 天 |
| Worker 注册重构 | P2 | 中 | 中 | 3-5 天 |
| 结构化日志 | P2 | 低 | 中 | 2-3 天 |
| 异步优化 | P2 | 高 | 高 | 2-3 周 |
| 事件通道隔离 | P1 | 中 | 中 | 3-5 天 |
| 优先级算法优化 | P2 | 低 | 低 | 1 天 |

---

## 📝 实施路线图

### Phase 1: 基础工程化 (1 周)
- [ ] 添加 pyproject.toml
- [ ] 配置代码质量工具 (Ruff, MyPy, Pre-commit)
- [ ] 添加 Makefile
- [ ] 增强 CI/CD

### Phase 2: 核心功能完善 (2 周)
- [ ] 修复线程安全问题
- [ ] 实现 Worker 延迟时间管理
- [ ] 重构 Worker 注册机制
- [ ] 实现 Plugin 系统基础

### Phase 3: 质量提升 (2 周)
- [ ] 完善测试覆盖
- [ ] 添加结构化日志
- [ ] 实现事件通道隔离
- [ ] 优化优先级算法

### Phase 4: 高级特性 (可选)
- [ ] 异步 Worker 支持
- [ ] SVM Worker 实现
- [ ] 状态机持久化优化

---

## 💡 最佳实践建议

1. **代码风格**: 遵循 PEP 8，使用 Ruff 自动格式化
2. **类型注解**: 所有公共 API 添加类型注解
3. **文档**: 使用 Google Style Docstring
4. **测试**: 新功能必须伴随单元测试
5. **提交信息**: 遵循 Conventional Commits 规范
6. **版本管理**: 使用 Semantic Versioning

---

*文档生成时间: 2026-02-12*  
*分支: feat-xmeng*
