# Zoo Framework 文档

!!! info "使用者请看另一个站点"
    **面向使用者的文档在 <https://yearsalso.github.io/zoo-framework-doc/>**（中英双语）
    —— 安装、教程、核心概念、API 参考。

    本目录是**维护者与贡献者文档**：架构、目录结构、调试、贡献规范、品牌规范、性能基准。

**进程内任务编排：调度、可观测、有状态 —— 不需要 broker，不需要 cron 守护进程。**

Zoo Framework 让你在**自己的进程里**运行长期存活的后台任务。你用一个类声明任务单元
（Worker），框架负责调度、并发去重、超时熔断、优雅停机与状态持久化。

它**不是**一个任务队列，也**不是**一个 Web 框架。没有 HTTP 层、没有 broker、没有分布式调度。
它是同一件事的进程内版本：一个调度器、一条事件管道、一个状态存储，嵌在你的服务里。

---

## 安装

```bash
pip install zoo-framework
```

需要 **Python 3.11+**（下界依据见[开发指南](contributing/development.md)）。

---

## 五分钟上手

把下面这段存成 `main.py` 然后运行：

```python
from zoo_framework.core import Master
from zoo_framework.workers import BaseWorker


class MyWorker(BaseWorker):
    """一个循环执行的任务单元。"""

    def __init__(self):
        super().__init__(
            {
                "is_loop": True,  # 跨调度轮次持续运行
                "delay_time": 1.0,  # 每轮执行后等待的秒数
                "name": "MyWorker",
            }
        )
        self.counter = 0

    def _execute(self):
        self.counter += 1
        print(f"[MyWorker] tick #{self.counter}")


if __name__ == "__main__":
    master = Master()
    master.register_worker("MyWorker", MyWorker)  # 注册的是**类**，见下
    master.run()
```

```bash
$ python main.py
[MyWorker] tick #1
[MyWorker] tick #2
[MyWorker] tick #3
...
```

`Master()` 默认读取工作目录下的 `./config.json`，**没有这个文件也能跑**。

> **Worker 必须以「类」注册。** `WorkerRegistry` 用 `issubclass` 校验，传入函数或实例会得到
> `TypeError: issubclass() arg 1 must be a class`。任何把类替换成工厂函数的装饰器都会触发
> 同样的错误——这是本项目历史上踩过的坑，因此容器刻意**不替换类**。

想生成带目录结构的项目，用脚手架：

```bash
zfc --create myapp         # -> myapp/src/{main.py,workers,conf,params,events}
cd myapp
zfc --worker order_sync    # 生成 src/workers/order_sync_worker.py 并接入 main.py
python src/main.py
```

---

## 你在找哪一块

| 我想要… | 去哪里 |
|---|---|
| 不起 Redis 就跑后台任务 | [教程：五分钟上手](tutorial/01-quickstart.md) |
| 重启后任务状态能恢复 | [指南：状态持久化](guides/state-persistence.md) |
| 两个任务之间传消息 | [指南：事件管道](guides/event-pipeline.md) |
| 跨 Worker 共享实例，且不破坏类型契约 | [指南：容器](guides/container.md) |
| 任务卡住了怎么办 | [指南：超时与熔断](guides/timeouts.md) |
| 查具体 API 的签名与参数 | [API 参考](api/README.md) |
| 我要从旧版本迁移 | [迁移指南](MIGRATION.md) |
| 它和 Celery / APScheduler 有什么区别 | [对比](guides/comparison.md) |
| 让 AI agent 生成的任务代码出错时能被拦住 | [为 AI 生成代码而设计](#for-ai-generated-code) |

---

## 我们做什么 / 明确不做什么

这张表是**范围声明，不是记分牌**：

| | Zoo Framework | Celery | APScheduler |
|---|---|---|---|
| 部署形态 | 嵌入你的进程 | 独立 worker + broker | 嵌入 |
| 外部依赖 | **无** | 需要 Redis/RabbitMQ | 无 |
| 跨机器 | ❌ | ✅ | ❌ |
| 多进程 | ❌ **未实现** | ✅ | ❌ |
| cron 表达式 | ❌（固定 `delay_time` 轮询） | ✅ beat | ✅ |
| 事件管道 / 优先级 / 重试 / 死信 | ✅ | 部分（队列） | ❌ |
| 内建状态持久化 | ✅ 原子替换 + 滚动备份 | 依赖 result backend | 依赖 job store |
| 失败方式 | **大声报错** | 多数明确 | 多数明确 |

**需要跨机器时用 Celery，这是正确答案。需要 cron 表达式时用 APScheduler。**
本框架**刻意不做**这两件事，它赢的那一行是：**无外部依赖、无 broker、无 cron 守护进程，
但依然有调度、可观测、可持久化。**

本对照反映各项目的公开定位，**未做跨项目基准测试**。

### 其它明确的限制

| 能力 | 状态 |
|---|---|
| 多进程执行 | ❌ **未实现**。模式常量是占位，请求会被显式拒绝（`NotImplementedError`） |
| cron 表达式 | ❌ 不支持，只有固定 `delay_time` 轮询 |
| 健康监控指标链路 | ⚠️ 尚未接通，`get_health_report()` 恒返回 `execute_count: 0` |
| 超时处理 | ⚠️ **观察并停止派发，不强制终止**正在执行的 Worker |

---

## 为 AI 生成代码而设计 {#for-ai-generated-code}

扩展面被刻意做窄，使生成的代码短、可验证、且出错时**错得响亮**。

| 输入 | 行为 |
|---|---|
| 未实现的调度模式（如 `process`） | 抛 `NotImplementedError` |
| 配置里无法识别的 run-policy 名称 | 抛 `ValueError` |
| 导入不存在的公开名字 | `ImportError` |
| 文件编码不符合预期 | 发出一条点名该文件的警告 |

这一点对生成的代码比对人写的代码更重要：**agent 无法发现自己被静默降级了**，
而一个响亮的错误是它自我纠正所需要的信号。

---

## 文档导航

### 给使用者

| 文档 | 说明 |
|---|---|
| [安装](install.md) | 版本要求、依赖、可选扩展 |
| [教程](tutorial/README.md) | 从零到跑通，每步都有期望输出 |
| [指南](guides/README.md) | 按「我要做 X」组织的主题式说明 |
| [API 参考](api/README.md) | 从代码自动生成的签名、参数、返回值、异常 |
| [架构概览](ARCHITECTURE.md) | 模块布局与数据流 |
| [性能基准](benchmark.md) | 原始数据、测量方法，以及**我们输在哪一档** |
| [迁移指南](MIGRATION.md) | 破坏性变更的 before/after 与报错原文 |
| [版本政策](VERSION_POLICY.md) | 公开 API 的边界、弃用与兼容承诺 |
| [常见问题](FAQ.md) | — |

### 给贡献者

从 [贡献者文档](contributing/README.md) 开始：开发环境搭建、目录结构、调试指南、
贡献规范、品牌与视觉规范、路线图。完整规范在 [CONTRIBUTING_MAINTAINER.md](CONTRIBUTING_MAINTAINER.md)，
想找一件能立马上手的小活看 [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md)。

> **关于命名**：框架用动物园隐喻命名（Worker / Master / Waiter / Cage / Event /
> FIFO / Reactor / StateMachine），但**隐喻只影响命名，不影响语义**。若某个名字
> 不清楚，以功能名为准 —— 见 [架构概览](ARCHITECTURE.md) 与 README 的概念表。
