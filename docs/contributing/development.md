# 开发环境搭建

本指南帮助开发者快速搭建 Zoo Framework 的开发环境。

---

## 环境要求

| 项目 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.11 | 3.13 |
| pip | 21.0 | 最新 |
| Git | 2.30 | 最新 |

「最低版本」是 `pyproject.toml` 里 `requires-python` 声明的门槛，「推荐版本」是开发时
用的解释器版本（`.venv` 与 `.python-version` 就是它）。两者的依据见下一节。

---

## Python 下界的依据

门槛是 **3.11**，依据如下。**注意别把两种版本陈述混为一谈**：`.python-version` 里的
`3.13` 是"开发环境的解释器版本"，不是门槛。

### 结论怎么来的

1. **可行性扫描**：全仓 Python 源码里没有 3.11 之后才引入的语法或标准库用法——
   PEP 695 泛型与类型别名 0 处、`match` 0 处、3.12／3.13 专属标准库 API 0 处、
   `typing` 的 `Self` / `Never` / `override` / `TypeIs` 0 处。唯一的 3.11 硬依赖是测试里
   用的 `tomllib`（3.11 起进标准库）。
2. **更早的硬性约束**：有 40 多个文件在**没有** `from __future__ import annotations` 的
   情况下使用 PEP 604 注解（`X | None`）。注解在 import 期求值，所以下限被顶到 **3.10**。
3. **实跑验证**：在下界解释器上跑全量测试通过；在 3.10 上测试**连收集都失败**（缺
   `tomllib`）。自己复跑一遍：

   ```bash
   uv python install 3.11
   uv venv --python 3.11 .venv311
   uv pip install --python .venv311 click pyyaml python-dotenv pytest pytest-cov
   PYTHONPATH=. .venv311/bin/python -m pytest       # Windows 用 .venv311\Scripts\python.exe
   ```

   在 3.11.15（Windows）上实跑得到 1111 passed + 1 skipped；同一棵树在 3.13.14 上是
   1124 passed，差额是 3.13 才装得上的可选扩展模块用例。这次实跑还抓到一处**既有的**时限
   断言脆弱点：`tests/test_execution_time.py` 用"时限 0.05 + 睡眠 0.06"建立"已超时"前置，
   而 Windows 上 3.11／3.12 的 `time.monotonic()` 粒度约 15.6 ms，实测增量可能是 46.8 ms
   （量化到 3 个 tick，比时限还小），于是断言随相位偶发翻红（本机 3/20 次）——CI 新增的
   windows × 3.11 作业会踩到。处置是把余量放大到 0.19 s（时限 0.01／等待 0.2），规则与
   实测数字写在用例上方的注释里。

4. **商业理由**：门槛决定本框架能被哪些上游写进依赖。3.11 一次放开 3.11 与 3.12 两个仍在
   生产中的版本带，而且是零适配成本的最低点；再降到 3.10 就得给测试引入 `tomli` 依赖或
   条件导入——那是把"门槛成本"换成"依赖成本"，还让最老的支持版本跑不到供应链门禁。

### 门槛变了要一起改什么

`requires-python` 是唯一真源，下列位置都跟随它（`tests/test_doc_consistency.py` 断言这一
致性）：

| 位置 | 跟随方式 |
|---|---|
| `uv.lock` 的 `requires-python` | 跑 `uv lock` 更新；改完核对 diff 里没有无关的依赖升级 |
| `[tool.ruff] target-version` | `py311` 形式，与下界同版本 |
| `[tool.mypy] python_version` | 与下界同版本 |
| `.github/workflows/tests.yml` 的矩阵 | 必须包含下界，且 ubuntu / windows / macos 三平台各跑一次 |
| 文档里的门槛句（两份 README、贡献入口、安装页、本页、FAQ、版本政策……） | 措辞跟上下界 |

**有两类不要跟着改**：

- **测量环境声明**："bench 在 Python 3.13 上实测""迁移指南的报错原文取自 3.13"说的是
  *当时在哪个解释器上取数*，不是门槛——改掉就变成假话。
- **可选原生扩展的下界**（`native/pyproject.toml`，3.13+）：它是可选编译扩展、CI 不覆盖，
  跟降等于写一条无法验证的声明。它不抬高主包的门槛。

**提高门槛前，必须先把依据写在本节。** 一个既没有扫描结论、也没有下界解释器实跑记录的
门槛，就是这次被修掉的那种历史默认值。

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

- [ ] Python 3.11+ 已安装（推荐用 3.13，见「Python 下界的依据」）
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
