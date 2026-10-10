# 开发环境搭建

本指南帮助开发者快速搭建 Zoo Framework 的开发环境。

---

## 环境要求

| 项目 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.13 | 3.13 |
| pip | 21.0 | 最新 |
| Git | 2.30 | 最新 |

---

## 步骤一：克隆代码

```bash
# 克隆仓库
git clone https://github.com/YearsAlso/zoo-framework.git

# 进入目录
cd zoo-framework

# 切换到开发分支
git checkout feat-xmeng
```

---

## 步骤二：创建虚拟环境

### 使用 venv（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活（Linux/Mac）
source venv/bin/activate

# 激活（Windows）
venv\Scripts\activate
```

### 使用 conda

```bash
# 创建环境
conda create -n zoo python=3.13

# 激活
conda activate zoo
```

---

## 步骤三：安装依赖

### 方式一：安装开发版本（推荐）

```bash
# 安装项目及所有开发依赖
pip install -e ".[dev]"
```

这会安装：
- 项目本身（editable 模式）
- 所有开发工具（Ruff, MyPy, pytest 等）
- 测试工具（pytest-cov, pytest-asyncio 等）

依赖的唯一真源是 `pyproject.toml`（`[project.optional-dependencies]` 的
`dev` / `docs` extras）；项目不维护 `requirements*.txt` 并列清单。

### 验证安装

```bash
# 检查是否安装成功
python -c "import zoo_framework; print('✅ 安装成功')"

# 查看版本
python -c "from zoo_framework import __version__; print(__version__)"
```

---

## 步骤四：安装 Pre-commit Hooks

Pre-commit 会在提交代码前自动运行代码检查。

```bash
# 安装 hooks
pre-commit install

# 手动运行检查（可选）
pre-commit run --all-files
```

**包含的检查**：
- 基础检查（文件尾空格、合并冲突等）
- Ruff lint + format
- MyPy 类型检查
- Bandit 安全扫描

---

## 步骤五：运行测试

### 运行所有测试

```bash
pytest
```

### 运行特定测试

```bash
# 运行 Worker 相关测试
pytest tests/test_worker.py

# 运行状态机测试
pytest tests/test_state_machine.py

# 运行异步 Worker 测试
pytest tests/test_async_worker.py
```

### 覆盖率报告

```bash
# 生成 HTML 覆盖率报告
pytest --cov=zoo_framework --cov-report=html

# 查看报告
# Linux/Mac
open htmlcov/index.html
# Windows
start htmlcov/index.html
```

---

## 步骤六：代码检查

### Ruff（代码风格和 lint）

```bash
# 检查代码
ruff check zoo_framework

# 自动修复问题
ruff check zoo_framework --fix

# 格式化代码
ruff format zoo_framework

# 检查格式化
ruff format --check zoo_framework
```

### MyPy（类型检查）

```bash
# 类型检查
mypy zoo_framework

# 显示错误代码
mypy zoo_framework --show-error-codes
```

### Bandit（安全扫描）

```bash
# 安全扫描
bandit -r zoo_framework -c .bandit.yaml

# 生成 JSON 报告
bandit -r zoo_framework -f json -o bandit-report.json
```

---

## 步骤七：运行示例

### 基础示例

```bash
# 运行最小示例
python example/minimal.py

# 运行线程示例
python example/threads/demo_thread.py
```

### 创建自己的 Worker

```python
# my_worker.py
from zoo_framework.workers import BaseWorker
from zoo_framework.core import Master


class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 2, "name": "MyWorker"})

    def _execute(self):
        print("🚀 Hello from MyWorker!")


if __name__ == "__main__":
    master = Master()
    master.run()
```

运行：

```bash
python my_worker.py
```

---

## 调试技巧

### 1. 开启 DEBUG 日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

### 2. 使用 IDE 调试

#### VS Code

创建 `.vscode/launch.json`：

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        }
    ]
}
```

#### PyCharm

1. 打开项目
2. 右键点击要运行的文件
3. 选择 "Debug"

### 3. 使用 pdb

```python
def _execute(self):
    import pdb

    pdb.set_trace()  # 断点
    # ... 你的代码
```

---

## 构建和发布

### 构建包

```bash
# 安装构建工具
pip install build

# 构建
python -m build

# 输出在 dist/ 目录
ls dist/
```

### 发布到 PyPI（维护者）

```bash
# 安装 twine
pip install twine

# 上传到测试 PyPI
twine upload --repository testpypi dist/*

# 上传到正式 PyPI
twine upload dist/*
```

---

## 常见问题

### Q: 安装依赖时速度慢？

```bash
# 使用国内镜像
pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q: pre-commit 安装失败？

```bash
# 手动安装 pre-commit
pip install pre-commit
pre-commit install

# 如果 hooks 下载慢，可以跳过首次检查
git commit -m "your message" --no-verify
```

### Q: MyPy 报错太多？

项目正在逐步添加类型注解，暂时允许 MyPy 在 CI 中失败。本地开发时可以忽略部分错误：

```python
# type: ignore
```

### Q: 测试覆盖率不达标？

新代码建议达到 80%+ 覆盖率。运行：

```bash
pytest --cov=zoo_framework --cov-report=term-missing
```

查看未覆盖的代码行。

---

## 开发环境检查清单

- [ ] Python 3.13+ 已安装
- [ ] 虚拟环境已创建并激活
- [ ] `pip install -e ".[dev]"` 成功
- [ ] `pre-commit install` 成功
- [ ] `pytest` 通过
- [ ] `ruff check zoo_framework` 通过
- [ ] 示例代码可以正常运行

---

## 下一步

- 📖 阅读 [架构设计](../ARCHITECTURE.md)
- 📝 查看 [贡献指南](contributing.md)
- 🐛 学习 [调试技巧](debugging.md)
- 📊 参考 [API 文档](../api/examples.md)
