## Why

`bench/` 与 zoo-bench 的实测证明：框架当前形态下真正的大头开销可以用**纯 Python 改动**拿回，量级（12x–800x）远大于 Rust 能带来的上限（1.67x，`bench/DECISION.md` no-go）。`adopt-rust-core` 的 tasks 1.3 已把这四项裁定归属本变更（默认启用资源池一项已随 `scheduler-model-seam` 落地）：

- **事件管道去 gevent**：`workers/event_worker.py` 的 `gevent.spawn` + `joinall` 实测单次投递 38.1 µs，是热路径上最大的原语错配
- **状态写路径去 gevent**：`statemachine/state_node.py` 的 `_perform_effect` 同一行既是性能问题，也是"写路径阻塞等待观察者最长 5 秒"的语义问题——两处 MUST 一起清掉，gevent 才能从依赖中移除
- **`ThreadSafeDict` 换锁**：模块级单把 `multiprocessing.Lock` 把全进程串行化（2056 ns vs `threading.RLock` 155 ns，13x）；换锁 MUST 连作用域一起换（按实例），与 `scoped-container` 的"线程安全归属必须显式声明"（#50）是同一条线
- **`BaseFIFO` 换 `deque`**：`list.pop(0)` 为 O(n)，队列 10k 时与 `deque` 差 12.4x

另外两件事依赖「去 gevent」这一动作：

- **free-threading 前置**：`gevent` / `greenlet` 在 no-GIL 构建（3.13t）上不可用。#47 登记的"无 GIL 构建"候选要走"zoo-bench 加 cp313t 目标"的测量路线，本变更是它的硬前置
- **#34 自然关闭**：`uv.lock` 里 greenlet 3.0.3 无 cp313 轮子导致 `uv sync` 在 3.13 上失败——greenlet 随 gevent 一起离开依赖树后该问题不复存在

`bench/` 至今**不在任何 CI 作业运行**（`tests.yml` L55-62 的注释记录了死 benchmark 作业已删），800x / 13x / 12.4x 只在 Windows 上成立；`DECISION.md` 的"未完成项"里原生 Linux 与 macOS 取数均待 CI。本变更一并承接。

## What Changes

**三项原语替换（行为语义逐项保持，无公共 API 变化）**

- `EventWorker`：`gevent.spawn/joinall` → 实例级 `ThreadPoolExecutor` + `concurrent.futures.wait(timeout)`；join 超时后未完成与执行异常的响应器均记日志（补齐 greenlet 吞异常的观测缺口）
- `StateNode._perform_effect`：`gevent.spawn/joinall(timeout=5)` → 模块级共享线程执行器 + `wait(timeout=5)`；"写路径同步等待 effect"语义**刻意保留**，非阻塞化属另行裁定的行为决策
- `ThreadSafeDict`：模块级 `multiprocessing.Lock` → **每实例一把 `threading.RLock`**
- `BaseFIFO` / `DelayFIFO`：`list` + `pop(0)` → `collections.deque` + `popleft()`（API 签名与空队返回 None 语义不变）

**依赖收口（BREAKING：运行依赖移除 gevent）**

- `pyproject.toml` / `requirements.txt` 移除 gevent；重跑 `uv lock`，greenlet / zope-event / zope-interface 离开依赖树
- 直接依赖"gevent 会被框架顺带装上"这一副作用的使用者需自行声明

**CI 与测量**

- 框架仓库新增 `bench.yml`：三平台（ubuntu / macOS / windows）手动 + 定时运行 `bench/` 非 Rust 测量脚本，结果留档为构件；不门禁 PR
- zoo-bench（跨仓库关联任务）：增加 3.13t free-threaded 构建目标，只测 `@dev`；留档目录带解释器 tag；决策门槛沿用 15% 阈值

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `event-dispatch`：消费路径的投递原语显式线程化并禁 greenlet；新增"join 超时与响应器异常 MUST 可观测"
- `state-machine`：新增"effect 以线程原语并发执行、写路径有界等待、异常不传播但可观测"
- `lock-primitives`：新增"ThreadSafeDict 每实例持锁、锁为 threading 级"
- `ci-and-packaging`：新增"bench 三平台原生取数"；"开发环境安装 MUST 可复现"补充 greenlet 系包出树的场景

## Impact

- **代码**：`zoo_framework/workers/event_worker.py`、`zoo_framework/statemachine/state_node.py`、`zoo_framework/utils/thread_safe_dict.py`、`zoo_framework/fifo/base_fifo.py`、`zoo_framework/fifo/delay_fifo.py`
- **依赖与元数据**：`pyproject.toml`、`requirements.txt`、`uv.lock`、`mkdocs.yml` 注释
- **CI**：框架仓库新增 `.github/workflows/bench.yml`；zoo-bench 仓库 `bench.yml` / `environment.py` / `storage.py` / `matrix.yaml`（跨仓库）
- **测试**：`tests/test_event.py`、状态机用例、`tests/test_utils*.py`、`tests/test_fifo.py` / `test_base_fifo.py` 补断言；全量 662 条只增不减
- **文档**：README / docs 中"基于 gevent 并发"的表述更新
- **issue 联动**：#31（承接锚点，本变更后关闭）、#34（随 gevent 出树关闭）、#47 P2（合入后另起切片）、#50（锁作用域与之合验）、`adopt-rust-core` 未完成项两行（bench CI 取数）回填
