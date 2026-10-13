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
| [`fastapi/app.py`](fastapi/app.py) | 把 Worker **嵌进 Web 服务**：lifespan 启动 Master，`POST /tick` 投递事件、`GET /state` 观察闭环 | `pip install fastapi uvicorn`，再 `cd fastapi && uvicorn app:app --port 8000` | 终端 `[heartbeat_worker] round #N` 递增；`curl -X POST localhost:8000/tick` 后出现 `[on_tick] handled 'tick-…'`，`curl localhost:8000/state` 返回两个计数 |

按 `Ctrl-C` 停止所有示例（`Master.run()` 阻塞在调度循环上）。

> 输出被重定向到管道或文件时，CPython 默认**块缓冲**会推迟 `print` —— 在终端里运行、
> 或用 `python -u`，就能即时看到。

## 关于 `agent/`

`agent/` 是指向姊妹仓库
[`zoo-code-agent`](https://github.com/YearsAlso/zoo-code-agent) 的 git
submodule —— 它是**可运行的最小 coding agent 消费方**，也是框架 Agent 线需求的实测来源，
不是随附示例。

**它做了什么**：一个 prompt 进入，经模型产出工具调用、执行工具、把观察回灌，直到命中预算或
截止期。工具调用**经框架事件管道派发**（不是在 Worker 体内直调）；会话记录与幂等账本经框架
状态机落盘，因此**进程重启后可续跑**，而被重放的付费工具调用不会产生第二次副作用。
工具面覆盖读 / 检索 / 写 / 精确编辑 / 执行命令，其中写与执行**每次都要过权限门**（失败关闭：
没有审批者就拒绝），代码求值能力一律不提供。端到端验收是「跑测试失败 → 读码 → 改码 → 跑测试
通过」，不需要任何模型 API 密钥。

**为什么它挂在这里**：README 的「面向 AI Agent 的代码生成」在此之前只有声明、没有凭据。这个
仓库把推断变成可证伪的实测——它跑出的三个框架缺口已登记为 issue #72 / #73 / #74，其中 #72、
#73 已修复并随 0.12.0 发布。

- 普通 `git clone` 后这里是**空目录**——这不是坏了， submodule 没被拉取而已。
- 补全它：
  ```bash
  git submodule update --init example/agent
  ```
  （或者干脆不带它：克隆时省掉 `--recursive` 也完全不影响其它示例。）

**怎么跑**（它只消费**已发布**的框架版本，当前 `>=0.12,<0.13`，刻意不跟 `dev` 主干——
消费方跟着主干跑，就失去了「发布版能不能用」这一层验证）：

```bash
git submodule update --init example/agent
cd example/agent
pip install -e ".[dev]"
pytest                       # 101 条用例，不需要任何模型 API 密钥
python src/main.py           # 起调度器，跑示例 Worker
```

它的布局就是**标准脚手架形态**（`src/main.py` + `workers/conf/params/events`），所以
`zfc --worker` 在那个仓库里可以直接用。零密钥跑一条会话：

```bash
python src/main.py -p "看看目录" --script examples/smoke.json --allow list_dir
```

它还会把工作目录里的 `AGENTS.md` / `CLAUDE.md` 注入系统提示，并在历史变长时把中间那段折叠成
一条摘要观察（**只改模型可见视图，存档保持完整**）——项目约定因此不必每次复述。

**实测数字**：同一批脚本化会话，开启事件推模型（`event:pushModelEnabled`）后单次会话端到端
由 5205 ms 降到 207 ms（25.3×）；对照脚本在
[`example/agent/bench/measure_session_latency.py`](agent/bench/measure_session_latency.py)。

## 运行位置说明

`main.py` 用 `from threads import DemoThread` —— 请在 `example/` 目录下运行它；
`threads/demo_thread.py`、`event/demo_event.py`、`minimal.py` 在各自目录运行即可。
`Master()` 默认读当前工作目录的 `./config.json`，没有也能跑。

`fastapi/app.py` 需要先 `pip install fastapi uvicorn`（**不是**本框架的依赖，故不写进
`pyproject.toml`）：在该文件所在目录运行 `uvicorn app:app --port 8000`。
