# 01 · 五分钟上手

**目标**：装好框架，写出第一个任务单元，亲眼看到它在跑。

## 1. 安装

```bash
pip install zoo-framework
```

需要 **Python 3.13+**。验证：

```bash
python -c "import zoo_framework; print(zoo_framework.__version__)"
```

## 2. 先做一件事：把日志调安静

新建一个工作目录，在里面放一个 `config.json`：

```json
{ "log": { "path": "./logs", "level": "warning" } }
```

**为什么要这一步**：不配置的话，框架会在控制台打印每个 Worker 每一轮的启停日志，
你的输出会被淹掉。实测对比见[教程首页](README.md#log-level-tip)。

> 这一步是可选的——不配也能跑，只是输出会比较吵。

## 3. 写第一个任务

在同一个目录里新建 `main.py`：

```python
from zoo_framework.core import Master
from zoo_framework.workers import BaseWorker


class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__({
            "is_loop": True,      # 跨调度轮次持续运行
            "delay_time": 1.0,    # 每轮执行后等待的秒数
            "name": "MyWorker",
        })
        self.counter = 0

    def _execute(self):
        self.counter += 1
        print(f"[MyWorker] tick #{self.counter}")


if __name__ == "__main__":
    master = Master()
    master.register_worker("MyWorker", MyWorker)
    master.run()
```

## 4. 运行

```bash
python -u main.py
```

> **为什么加 `-u`**：当输出被重定向到管道或文件时，Python 默认会**块缓冲** `print`，
> 你会看不到实时输出。`-u` 关掉缓冲。直接在终端里跑则不需要。

**期望输出**：

```
[MyWorker] tick #1
[MyWorker] tick #2
[MyWorker] tick #3
...
```

按 `Ctrl-C` 停止。

## 5. 这段代码在做什么

| 部分 | 作用 |
|---|---|
| `class MyWorker(BaseWorker)` | 一个任务单元。你只实现 `_execute()` |
| `super().__init__({...})` | 声明这个任务的属性：循环、间隔、名字 |
| `is_loop: True` | 每轮调度结束后重新排回队列（不设则只跑一次） |
| `master.register_worker("MyWorker", MyWorker)` | **注册类**，不是注册实例 |
| `master.run()` | 加载配置、启动调度、阻塞运行 |
| `Master()` | 无参构造会读工作目录的 `./config.json`，**没有也能跑** |

## 常见错误

### `TypeError: issubclass() arg 1 must be a class`

```python
master.register_worker("MyWorker", MyWorker())     # ❌ 传了实例
master.register_worker("MyWorker", lambda: MyWorker())  # ❌ 传了工厂函数
```

**原因**：`WorkerRegistry` 用 `issubclass` 校验注册对象。任何把类替换成函数或实例的写法
都会失败——包括某些用装饰器"包装类"的库。

**修法**：传类本身。

### `AttributeError: property 'is_loop' of 'MyWorker' object has no setter`

```python
def __init__(self):
    super().__init__({...})
    self.is_loop = True     # ❌
```

**原因**：`is_loop` 是只读属性，唯一真源是构造时传入的 `_props`。

**修法**：在 `super().__init__(...)` 的字典里声明它。

### 看不到任何输出

三件事依次排查：

1. 加 `python -u`（见上）
2. 确认 `log.level` 没被设成 `error` 以上
3. 确认真的是在注册之后调用 `master.run()`——`Master()` 单独构造只跑两个内建系统 Worker，
   不会跑你的任务

### `ModuleNotFoundError: No module named 'zoo_framework'`

装到了别的解释器里。用 `python -m pip install zoo-framework` 确保与你运行时用的是同一个
解释器。

## 下一步

- [02 状态持久化](02-state-persistence.md) —— 让 `counter` 在重启后接着数
- [指南](../guides/README.md) —— 按"我要做 X"组织
