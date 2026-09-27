# 发布说明要点

`release.yml` 的 GitHub Release 正文由 `git log` 的提交信息生成，因此下方内容
MUST 写入对应提交的 **commit message 正文**。

---

## 修复 · `zfc` 脚手架此前产出的项目无法运行

一次完整生成（`zfc --create` + `zfc --worker`）在四个环节全部断开：

| 环节 | 修复前的表现 |
|---|---|
| 生成的 Worker 文件 | `ImportError: cannot import name 'worker' from 'zoo_framework'` |
| 生成的入口 | `Master(worker_count=5)` → `TypeError: unexpected keyword argument` |
| 生成的 Worker 注册 | `@worker(count=1)` 写入的注册表没有任何消费者，导入成功也不会被调度 |
| Worker 的加载 | 包初始化文件里写了一行导入语句，但没有任何代码导入该包，语句从不执行 |

**修复后**，生成的项目可以直接启动：

```bash
zfc --create myapp
cd myapp
zfc --worker my_task
python src/main.py
```

**新旧产物对照**

```python
# 修复前 · src/workers/my_task_worker.py
from zoo_framework import worker          # ← 该名称在包根不存在
@worker(count=1)                          # ← 注册进没有消费者的注册表
class My_TaskWorker(BaseWorker): ...

# 修复后 · src/workers/my_task_worker.py
from zoo_framework.workers import BaseWorker
class My_TaskWorker(BaseWorker): ...
```

```python
# 修复前 · src/main.py
master = Master(worker_count=5)           # ← 参数不存在

# 修复后 · src/main.py
from workers.my_task_worker import My_TaskWorker
WORKERS = [("My_TaskWorker", My_TaskWorker)]
master = Master()
for name, worker_class in WORKERS:
    master.register_worker(name, worker_class)
```

**对已有项目的影响**：脚手架产出的是用户资产，框架不做原地升级。已用旧版生成的
项目需要按上面的对照手工调整，或重新生成。

---

## BREAKING · `zfc --config` 被移除

该选项此前被命令行接受、但在命令实现体内零引用，即静默忽略。现已移除；传入它会
明确报错 `No such option`。由于它此前不产生任何效果，移除不改变任何既有可用行为。

---

## 其他

- **`src/` 被补上包标识**：产出项目此前只有 `src/` 的子目录有 `__init__.py`，包结构不自洽
- **模板示范的钩子全部名副其实**：`_execute` / `_destroy` / `_on_error` / `_on_done`
  四个钩子现在都确实会被框架调用（`_destroy` 由停机流程触发）
- **`zoo_framework.templates.worker_mod_insert_template` 被移除**：它用于往包初始化
  文件里塞一行从不执行的导入，修复后不再需要
