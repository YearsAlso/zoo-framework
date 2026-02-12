# 📝 贡献指南

感谢您对 Zoo Framework 的兴趣！本文档帮助您了解如何为项目做出贡献。

---

## 🤝 贡献方式

- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 改进文档
- 🔧 提交代码修复
- 🧪 添加测试用例

---

## 🚀 开发流程

### 1. Fork 仓库

```bash
# Fork 项目到自己的账号
# 然后克隆 fork 的仓库
git clone https://github.com/YOUR_USERNAME/zoo-framework.git
cd zoo-framework
```

### 2. 创建分支

```bash
# 从 main 分支创建功能分支
git checkout -b feat/your-feature-name

# 或修复分支
git checkout -b fix/bug-description
```

**分支命名规范**：

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feat/` | 新功能 | `feat/async-worker` |
| `fix/` | Bug 修复 | `fix/memory-leak` |
| `docs/` | 文档更新 | `docs/api-reference` |
| `refactor/` | 代码重构 | `refactor/worker-registry` |
| `test/` | 测试相关 | `test/state-machine` |

### 3. 开发和测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 安装 pre-commit
pre-commit install

# 运行测试
pytest

# 代码检查
ruff check zoo_framework --fix
mypy zoo_framework
```

### 4. 提交代码

```bash
# 添加更改
git add .

# 提交（pre-commit 会自动运行检查）
git commit -m "feat: 添加异步 Worker 支持"

# 推送到 fork
git push origin feat/your-feature-name
```

### 5. 创建 Pull Request

1. 访问原仓库：https://github.com/YearsAlso/zoo-framework
2. 点击 "New Pull Request"
3. 选择你的分支和 main 分支
4. 填写 PR 描述

---

## 📋 代码规范

### Python 代码风格

我们使用 **Ruff** 进行代码检查和格式化：

```bash
# 检查
ruff check zoo_framework

# 自动修复
ruff check zoo_framework --fix

# 格式化
ruff format zoo_framework
```

### 类型注解

鼓励添加类型注解，但不是强制要求：

```python
from typing import Optional, Dict, Any

def process_data(data: Dict[str, Any]) -> Optional[str]:
    """处理数据并返回结果。
    
    Args:
        data: 输入数据字典
        
    Returns:
        处理结果，失败返回 None
    """
    if not data:
        return None
    return str(data)
```

### 文档字符串

使用 Google 风格：

```python
def my_function(param1: int, param2: str) -> bool:
    """函数简短描述。
    
    更详细的描述...
    
    Args:
        param1: 参数1的说明
        param2: 参数2的说明
        
    Returns:
        返回值的说明
        
    Raises:
        ValueError: 当参数无效时
        
    Example:
        >>> my_function(1, "test")
        True
    """
    return True
```

---

## 📝 提交信息规范

### 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 类型 (Type)

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: 添加异步 Worker` |
| `fix` | Bug 修复 | `fix: 修复内存泄漏` |
| `docs` | 文档更新 | `docs: 更新 API 文档` |
| `style` | 代码格式 | `style: 格式化代码` |
| `refactor` | 重构 | `refactor: 重构 Worker 注册` |
| `test` | 测试 | `test: 添加状态机测试` |
| `chore` | 构建/工具 | `chore: 更新依赖` |
| `perf` | 性能优化 | `perf: 优化优先级算法` |

### 范围 (Scope)

可选，表示影响的模块：

- `worker`
- `statemachine`
- `fifo`
- `reactor`
- `plugin`
- `core`
- `docs`

### 示例

```bash
# 新功能
feat(worker): 添加 AsyncWorker 支持协程执行

实现了 AsyncWorker 基类，支持：
- 原生 asyncio 协程
- 自动事件循环管理
- 并发限制

Closes #123

# Bug 修复
fix(statemachine): 修复状态机持久化时的竞态条件

添加 RLock 保护文件操作，防止并发写入冲突。

Fixes #456

# 文档
docs(api): 更新 Worker API 文档

添加 AsyncWorker 使用示例和最佳实践。
```

---

## 🧪 测试规范

### 测试文件位置

```
tests/
├── test_worker.py
├── test_state_machine.py
├── test_fifo.py
└── conftest.py  # 共享 fixture
```

### 测试命名

```python
# ✅ 好的命名
def test_worker_execute_returns_result():
def test_state_machine_transition_success():
def test_fifo_priority_sorting():

# ❌ 避免
def test1():
def worker_test():
```

### 测试结构

```python
import pytest
from zoo_framework.workers import BaseWorker


class TestBaseWorker:
    """BaseWorker 测试类"""
    
    def test_init_sets_default_values(self):
        """测试初始化设置默认值"""
        worker = BaseWorker()
        assert worker.is_loop is False
        assert worker.delay_time == 0
    
    def test_execute_raises_not_implemented(self):
        """测试未实现 _execute 时抛出异常"""
        worker = BaseWorker()
        with pytest.raises(NotImplementedError):
            worker._execute()
    
    @pytest.mark.parametrize("delay_time", [0.1, 1.0, 5.0])
    def test_delay_time_variations(self, delay_time):
        """测试不同延迟时间"""
        worker = BaseWorker({"delay_time": delay_time})
        assert worker.delay_time == delay_time
```

### 覆盖率要求

- 新代码：建议 80%+ 覆盖率
- 关键路径：必须 100% 覆盖

---

## 📚 文档规范

### 代码注释

```python
# ✅ 好的注释
# 使用指数退避策略，避免频繁重试
time.sleep(2 ** attempt)

# ❌ 避免
# 睡眠
sleep(2 ** attempt)
```

### 文档更新

修改代码时同步更新相关文档：

- `docs/` - 开发者文档
- `docstrings` - API 文档
- `README.md` - 项目说明
- `CHANGELOG.md` - 变更日志

---

## 🔍 Code Review 流程

### Reviewer 检查清单

- [ ] 代码符合项目规范
- [ ] 有足够的测试覆盖
- [ ] 文档已更新
- [ ] 提交信息规范
- [ ] 无安全漏洞

### 回复 Review 意见

```bash
# 1. 查看意见并修改代码
# 2. 添加修改到暂存区
git add .

# 3. 修改提交（保持提交历史整洁）
git commit --amend --no-edit

# 4. 强制推送（仅用于 PR 分支）
git push --force-with-lease origin feat/your-feature-name
```

---

## 🐛 报告 Bug

### Bug 报告模板

```markdown
## 描述
清晰描述 Bug 是什么

## 复现步骤
1. 步骤 1
2. 步骤 2
3. 步骤 3

## 期望行为
描述期望的正确行为

## 实际行为
描述实际发生的错误行为

## 环境信息
- Python 版本：
- 操作系统：
- 框架版本：

## 代码示例
```python
# 最小复现代码
```

## 错误日志
```
粘贴错误日志
```
```

---

## 💡 提出新功能

### 功能请求模板

```markdown
## 功能描述
描述你想要的功能

## 使用场景
描述这个功能在什么场景下有用

## 期望的 API
```python
# 示例代码
```

## 替代方案
描述你考虑过的替代方案

## 其他信息
任何其他相关信息
```

---

## 🎯 贡献者行为准则

- 尊重所有贡献者
- 欢迎新手提问
- 建设性反馈
- 专注于技术讨论
- 遵守开源许可证

---

## 📞 获取帮助

- 📖 阅读 [开发文档](DEVELOPMENT.md)
- 🏗️ 查看 [架构设计](ARCHITECTURE.md)
- 🐛 学习 [调试技巧](DEBUGGING.md)
- 💬 在 Discussion 中提问

---

## 🙏 致谢

感谢所有为 Zoo Framework 做出贡献的开发者！
