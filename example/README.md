# 示例目录

每个示例演示框架的一个面向。都以**复制即跑**为目标：装好框架
（`pip install zoo-framework` 或 `pip install -e ".[dev]"`），在文件所在目录直接
`python <文件>` 即可。

| 文件 | 演示什么 | 怎么跑 | 期望输出 |
|---|---|---|---|
| [`minimal.py`](minimal.py) | 最小完整程序：一个循环 Worker，每秒打印一行 | `python minimal.py` | `Hello from MyWorker! Count: 1, 2, 3…`（框架自身的启停日志走日志通道，长得不一样） |
| [`main.py`](main.py) | Worker + **状态机**组合：DemoThread 每一轮读、写、观察一个状态键 | `python main.py` | `Test get i:[N], self.i:[N]` 逐秒递增；首轮从 `.pic` 存档加载（没有则提示创建） |
| [`threads/demo_thread.py`](threads/demo_thread.py) | `main.py` 的那个 Worker 单独运行（同一个类，带 `__main__` 入口） | `python threads/demo_thread.py` | 同 `main.py`（`Test get i:[N], …`） |
| [`event/demo_event.py`](event/demo_event.py) | 最小**事件管道**闭环：`@event` 注册 reactor → 后台线程投递 → reactor 被响应 | `python event/demo_event.py` | 3 行 `pushed event #N`，随后 3 行 `on_change_test_number:…`（reactor 收到） |

按 `Ctrl-C` 停止所有示例（`Master.run()` 阻塞在调度循环上）。

> 输出被重定向到管道或文件时，CPython 默认**块缓冲**会推迟 `print` —— 在终端里运行、
> 或用 `python -u`，就能即时看到。

## 关于 `agent/`

`agent/` 是指向姊妹仓库
[`zoo-code-agent`](https://github.com/YearsAlso/zoo-code-agent) 的 git
submodule —— 那是框架 Agent 线的消费者验证仓库，不是示例。

- 普通 `git clone` 后这里是**空目录**——这不是坏了， submodule 没被拉取而已。
- 补全它：
  ```bash
  git submodule update --init example/agent
  ```
  （或者干脆不带它：克隆时省掉 `--recursive` 也完全不影响其它示例。）

## 运行位置说明

`main.py` 用 `from threads import DemoThread` —— 请在 `example/` 目录下运行它；
`threads/demo_thread.py`、`event/demo_event.py`、`minimal.py` 在各自目录运行即可。
`Master()` 默认读当前工作目录的 `./config.json`，没有也能跑。
