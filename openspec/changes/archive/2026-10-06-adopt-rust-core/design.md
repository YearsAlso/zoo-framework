## Context

动机见 `proposal.md · Why`，此处只列影响技术选型的约束：

- **Worker 体是 Python 可调用对象**。框架的调度层只决定"谁、何时、在哪个执行单元上跑"，执行内容由用户实现。任何调度层改造都不改变这段代码的成本——这是上一轮评估的核心结论，也是本变更要重新检验其边界的假设。
- **运行时是标准 GIL 构建**。`requires-python = ">=3.13"`，本机 `sys._is_gil_enabled()` 返回 True。实测 4 线程跑 CPU 密集 Python 的加速比为 **0.94x**。混用架构解决的是"I/O 并发与调度开销"，**不是**"Python 代码并行"。
- **框架存在三套互不相通的并发模型**：Waiter 用裸 `threading.Thread` / `ThreadPoolExecutor`；事件管道用 `gevent`（实测**未**启用 monkey patch，`threading`/`socket`/`time` 均为 stdlib，即零真并发）；`AsyncWorker` 自带 `asyncio.run()`。
- **当前的热点已定位且在 Python 层可修**。本机实测：`ThreadPoolExecutor.submit().result()` 31.9 µs vs 裸 `queue.Queue` 1.86 µs → 派发开销中约 95% 是 `concurrent.futures` 的 Python 记账；`ThreadSafeDict` set+get 4.62 µs（`multiprocessing.Lock` 占绝大部分）；`gevent.spawn`+`joinall` 38.1 µs vs 直接调用 47.5 ns。**这些都在 `fix-worker-scheduling` 中修复，本变更必须在此之后取基线。**
- **构建与发布是纯 Python 链路**：`[build-system] requires = ["hatchling"]`，`release.yml:282` 用 `python -m build` 产出单个纯 Python wheel。
- **CI 覆盖三个平台**（ubuntu / windows / macos），且 ruff 与 pytest 是硬门禁。

## Goals / Non-Goals

**Goals:**

- 用可复现的实测数据回答一个问题：**在目标负载下，框架自身开销占端到端延迟的比例是多少？**
- 验证 PyO3 边界的三项关键成本：穿越开销、GIL 释放/重获代价、Rust 回调 Python 的真实成本
- 验证崩溃隔离可行：Rust 侧 panic 不导致 Python 进程 abort
- 给出构建发布从 `hatchling` 迁移到 `maturin` 的完整路径与**可回退**方案
- 产出 go / no-go 决策及理由；no-go 是合法结论

**Non-Goals:**

- 不实现任何产品级 Rust 代码，不把 Rust 扩展发布给用户
- 不改动 `pyproject.toml` 的构建后端、不改动任何 workflow
- 不为"提升并发度"引入 free-threaded 构建或改变 `requires-python`
- 不在本变更内做调度层迁移（即便测量结论支持，实施也属 `adopt-rust-core-impl`）
- 不追求"比 uvicorn / granian 更快"这类横向对标；只回答"对本项目的目标负载是否值得"

## Decisions

### D0 · 测量 MUST 覆盖多平台，MUST NOT 以单平台数据定论

**背景**：本变更的立项论证（见 `fix-worker-scheduling · design.md` 的 Open Question）全部基于 Windows 单平台实测。补测 Linux 后，其中两项数字出现数量级差异，**足以改变结论**：

| 项 | Windows | Linux (WSL2, Debian / py3.13.5) | 倍率 |
|---|---|---|---|
| `multiprocessing.Lock` | 2063 ns | 181 ns | **11.4x** |
| `threading.RLock` | 155 ns | 114 ns | 1.4x |
| 裸 `dict.get` | 26 ns | 21 ns | 1.2x |
| **`multiprocessing.Lock` ÷ `RLock`** | **13.3x** | **1.6x** | — |
| 进程启动（线程 start+join） | 215 µs | 335 µs | — |
| 进程启动（进程 start+join） | **93 ms**（spawn） | **12 ms**（fork） | 7.75x |
| `list.pop(0)` vs `deque` @10k | 12.4x | 14.0x | 一致 |
| GIL 下 4 线程 CPU 密集加速比 | 0.94x | 0.94x | 一致 |

**两处结论需要修正**：

1. `fix-worker-scheduling` 把 `ThreadSafeDict` 的 `multiprocessing.Lock` 列为最大热点（依据 4.62 µs 的 set+get）。补测显示**这是 Windows 特有的缺陷**：Windows 上是 13.3x 的病灶，Linux 上只是 1.6x 的优化项。修复本身（换 `threading.RLock`）在两个平台都正确，但**优先级判断具有平台依赖性**。
2. D1 以"Windows 上进程 `spawn` 93 ms"为由拒绝了"进程隔离获得真超时"这一替代方案。Linux 的 `fork` 只需 12 ms，**该方案在 Linux 上远比在 Windows 上可行**。跨平台方案应是"能力探测 + 分级"，而非按最慢平台的数字一刀切。

**要求**：本变更的 profile 与边界成本测量 MUST 在**至少两个平台**上进行（Linux 与 Windows），macOS 至少做一次抽样验证。所有结论 MUST 标注其适用的平台范围；无法在两个平台都验证的结论 MUST 明确写为"单平台结论"。

**WSL 的用途边界**：WSL2 可用于验证**机制性**差异（锁的实现代价、`fork` 与 `spawn` 的有无、GIL 行为）——这些数字在 WSL 上方向正确且稳定。但 **WSL2 的跨 vCPU 线程唤醒延迟不可作为原生 Linux 的代表**：实测 `ThreadPoolExecutor.submit().result()` 在 WSL2 上为 82 µs，远高于 Windows 主机的 31.9 µs，这是 Hyper-V 调度器造成的伪影而非 Linux 的真实表现。任何涉及跨线程唤醒的绝对延迟，MUST 在原生 Linux runner（CI 的 `ubuntu-latest`）上取数。

### D1 · 异步运行时选 Tokio，不自建 mio 反应堆

**选择**：PoC 与后续实施均基于 Tokio 的多线程运行时。

**理由**：三个平台的 I/O 多路复用模型**不只是 API 不同，而是模型不同**——Linux 的 epoll 与 macOS 的 kqueue 是 *readiness* 语义（"可读了，你来读"），Windows 的 IOCP 是 *completion* 语义（"读完了，数据在这"）。自建反应堆意味着要为两套不同的模型各写一遍调度逻辑，并且要处理"epoll 下从其他线程唤醒事件循环"（`eventfd`）与"IOCP 下等价操作"（`PostQueuedCompletionStatus`）这类不对称问题。连接管理、定时器轮、背压、取消传播则全部现成。在价值尚未验证的阶段自建运行时，是用数倍工作量换取二进制的依赖可控性，属过早优化。

**已考虑的替代**：uvloop 式集成（不引入 Rust，用 libuv 接管事件循环）。拒绝理由——它不解决"Python 回调成本"这一根本项，且其大部分可及收益已被 `fix-worker-scheduling` 的纯 Python 优化覆盖；引入它的收益不足以支撑一条新的依赖链。

**跨平台备注**：Tokio 在 Windows 上的 IOCP 适配是本项目依赖它的最核心理由，而非风险点。真正需要在 PoC 中验证的跨平台项是**定时器精度**（Windows 默认定时器分辨率约 15.6 ms）。

### D2 · PyO3 边界收敛为唯一穿越点，且调用必须粗粒度

**选择**：全系统只保留两类跨界调用，且对单次请求的穿越次数给出上界并断言。

| 方向 | 形态 | 频率 |
|---|---|---|
| Python → Rust | `submit` / `push` / `subscribe` / `serve` | 低频，粗粒度（一次调用完成多件事） |
| Rust → Python | 执行 Worker 体 / 调用响应器 | **唯一的高频穿越** |

**约束**：

- 单次请求的边界穿越次数 MUST 有上界，且该上界 MUST 可由测试断言，而非口头约定
- 热路径上 MUST NOT 做逐字段的属性读写——每次 `getattr` 都是一次穿越。Rust 侧需要状态时，MUST 通过一次性快照或事件推送获得，MUST NOT 让 Python 轮询查询
- 跨边界只传基本类型与 `bytes`；结构化数据在 Rust 侧由 serde 处理，MUST NOT 依赖 Python 的 `pickle`
- Rust 侧所有不涉及 Python 对象的工作 MUST 用 `Python::allow_threads` 包裹

**已考虑的替代**：细粒度 API（Python 频繁查询 Rust 侧状态、逐字段读写）。拒绝理由见下方实测数据——该约束方向正确，但**原先的量化依据被高估了约 11 倍**，此处修正。

#### 实测数据（任务组 3 的产出）

探针：`bench/pyo3_probe`（PyO3 0.23，release，`panic = "unwind"`）。
测量脚本：`bench/measure_boundary.py`，结果落在 `bench/results/boundary_<platform>.json`。

| 项 | Windows-AMD64 | Linux-x86_64 (WSL2) |
|---|---|---|
| Python→Rust 空调用往返 | **28.9 ns** | **23.9 ns** |
| Rust→Python 回调（持 GIL） | 63.5 ns | 48.2 ns |
| `Python::allow_threads` 往返 | 63.9 ns | 63.4 ns |
| 纯 Python 空调用（参照） | 27.4 ns | 20.8 ns |
| 细粒度：1000 件事逐次跨界 | 25,363 ns | 17,467 ns |
| 粗粒度：一次跨界 + Rust 侧做 1000 件事 | 780.5 ns | 756.6 ns |
| **粗细粒度比值** | **32.5x** | **23.1x** |

**三条修正性结论**：

1. **PyO3 的边界穿越成本可以忽略**：28.9 ns 与纯 Python 空调用（27.4 ns）几乎相同。
   原 D2 论据引用的 0.33 µs（330 ns）是 **ctypes 的上界**，比 PyO3 实测高约 **11 倍**。
2. **"几十次往返就会吃掉调度层节省下的 12 µs"是错的**：按 28.9 ns/次计算，需要约
   **415 次**往返才能吃掉 12 µs，而不是几十次。D2 的"粗粒度"约束仍然成立，但它的
   真正依据是**每次穿越都伴随一次 Python 调用语义的成本**（Rust→Python 回调 63.5 ns），
   而非穿越本身昂贵。
3. **粗细粒度比值 32.5x** 是本次结论中最有分量的数字：同样做 1000 件事，
   逐次跨界比一次跨界慢 32 倍。这为 D2 提供了实测支撑，也说明**任何让 Python 侧
   参与内层循环的设计都应当被否决**。

**平台适用性**：两项测量都在两个平台上取数（D0 要求）。边界穿越成本与纯 Python
调用成本的**关系**在两个平台上一致（穿越 ≈ 一次 Python 调用），因此"穿越可忽略"
这一机制性结论跨平台成立。绝对数字的差异来自 WSL2 与原生 Windows 的运行时差异，
不改变结论。

#### 平台特性实测：Windows 定时器分辨率（任务 3.6）

探针：`bench/measure_timer.py`，结果落在 `bench/results/timer_resolution_<platform>.json`。
表中数值为**相对目标时长的额外超时**（中位值，单位毫秒）。

| 目标时长 | Windows `time.sleep` | Windows `Event.wait` | Linux `time.sleep` | Linux `Event.wait` |
|---|---|---|---|---|
| 0.5 ms | 0.53 | **14.85** | 0.078 | 0.088 |
| 1.0 ms | 0.24 | **14.47** | 0.084 | 0.089 |
| 5.0 ms | 0.21 | **10.27** | 0.090 | 0.095 |

**结论**：

- Linux 上两类等待的抖动都只有 **~0.08–0.09 ms**，与目标时长无关。
- Windows 上 `time.sleep` 借助高精度可等待定时器可以做到**亚毫秒**精度，但
  **`threading.Event.wait` 的最低有效粒度约为 15 ms**（Windows 默认定时器 tick）。
- 同一操作在两个平台上的差异达 **约 170 倍**。

这为 D6 层 2 的"Windows 定时器分辨率"一条给出了具体数值，并产出一条工程约束：

> 在 Windows 上实现与短时长相关的等待时，MUST 使用 `time.sleep` 或可等待定时器，
> MUST NOT 依赖 `Event.wait` 的短超时——后者会被量化到约 15 ms。

（框架内 `SVMWorker` 用 `Event.wait(10)` 做可唤醒的监控间隔，10 秒量级不受影响；
任何**毫秒级**的调度等待都不能用该方式。这条约束在 P3 设计 Rust 侧的定时器轮时同样适用。）

### D3 · panic MUST NOT 导致进程 abort

**选择**：FFI 边界处用 `catch_unwind` 兜住所有 panic 并转换为 Python 异常；release profile 必须保持 `panic = "unwind"`。

**理由**：Rust 默认 release profile 是 `unwind`，但为减小二进制体积改成 `panic = "abort"` 是常见做法。对一个**调度器**而言，abort 会让整个服务进程静默消失——这是最坏的失败模式：没有堆栈、没有机会落盘状态、没有机会通知调用方。

**验证要求**：PoC MUST 包含一条必然 panic 的路径，并断言 Python 侧收到异常且进程存活。该断言是 go 的必要条件之一，且在**每个目标平台**上都必须通过（panic 跨 FFI 的展开行为存在平台差异）。

### D4 · 构建迁移到 maturin，但保留可回退的纯 Python 路径

**选择**：若实施，构建后端从 `hatchling` 迁移到 `maturin`，使用 `abi3-py313` 使单个 wheel 覆盖 3.13+ 的所有小版本。**同时保留纯 Python 实现作为可选加速的降级路径**：

```python
try:
    import zoo_core  # Rust 扩展（可选）

    HAS_RUST_CORE = True
except ImportError:
    HAS_RUST_CORE = False  # 回退到纯 Python 实现
```

**理由**：全量替换为 Rust-only 会失去可回退性，并强制所有用户安装带平台限制的二进制产物——对一个以"pip 可装、源码可读"为卖点的框架，这是产品属性的断裂。可选加速使迁移可增量、可随时回退，也让 CI 能在没有 Rust 工具链的环境下继续验证语义。

**已考虑的替代**：直接替换为 Rust-only。拒绝理由如上——不可回退是最大的问题，其次才是产物矩阵与用户安装成本。

**跨平台备注**：`abi3-py313` 只消除 **Python 版本**维度，**平台维度仍需枚举**。完整的产物矩阵与裁剪策略见 D6。

### D5 · 分阶段推进，每阶段有独立回滚点

| 阶段 | 内容 | 归属 | 结束时的可发布状态 |
|---|---|---|---|
| P1 | 语义修复 + 纯 Python 性能优化 | `fix-worker-scheduling` | 可发布，行为正确 |
| P2 | PoC + 测量 + go/no-go 决策 | **本变更** | 可发布（无行为变化），决策有数据支撑 |
| P3 | I/O 与协议层 Rust 化，调度语义仍留在 Python | `adopt-rust-core-impl` | 可发布，Rust 为可选加速，可回退 |
| P4 | 调度层迁移 | 视 P3 数据决定，可能不做 | — |

**P4 的启动条件是 P3 的实测数据**，MUST NOT 预设。基于已有测量（调度开销相对优化后的 Python 仅快 2–3x、绝对值 1–2 µs），P4 的预期结论是**不做**——除非 P3 暴露了新的瓶颈位置。注意该判断同样有 D0 所述的平台依赖：Linux 上调度层本就更便宜，P4 的收益比 Windows 上更低。

### D6 · 跨平台实现方案：依赖运行时封装，不建自建抽象层

**选择**：分三层处理平台差异。**优先依赖 Tokio 与 CPython 已封装的差异，只在语义确实不同处显式分支**，MUST NOT 在框架层自建一套"平台抽象层"——那会把三套平台逻辑变成四套。

**层 1 · 构建与分发**

- 工具链：`maturin` + `cibuildwheel`（后者原生支持 maturin 后端，统一管理容器、QEMU 与产物命名）
- `abi3-py313` 消除 Python 版本维度；平台维度靠 CI matrix 枚举
- **产物矩阵裁剪**：完整矩阵（linux×{manylinux_2_28, musllinux_1_2}×{x86_64, aarch64} + macos universal2 + windows×{x64, arm64} + sdist）约 10 个产物。**P3 建议先做 3 个**：`manylinux_2_28 x86_64`、`macos universal2`、`windows x64`，其余按实际下游需求增量补。理由：矩阵规模是长期维护成本的主要来源，而 aarch64 与 musl 的需求应被证实而非假设
- 交叉编译路径：Linux aarch64 走 maturin 的 manylinux 容器 + QEMU；macOS 用 `--target universal2-apple-darwin` 单产物覆盖两架构；Windows arm64 需要 `windows-11-arm` runner 或专用工具链，**P3 应先排除**，作为独立后续
- manylinux 基线选 `2_28`（glibc 2.28，对应 RHEL 8 / Debian 10+）。选 `2_17` 覆盖更老发行版，但需要更旧的构建容器；该取舍须在 P3 定稿前确认支持范围
- CI matrix 覆盖 4 个 runner：`ubuntu-latest`、`windows-latest`、`macos-13`（x86_64）、`macos-14`（arm64）

**层 2 · 平台语义差异（必须显式处理的部分）**

| 差异 | Linux | macOS | Windows | 方案 |
|---|---|---|---|---|
| 进程启动 | `fork` 12 ms | `spawn` | `spawn` 93 ms | **要求 Worker 可 pickle**以保证跨平台一致；`fork` 仅作 Linux 上的可选优化，且 MUST NOT 成为语义依赖 |
| 事件循环模型 | epoll（readiness） | kqueue（readiness） | **IOCP（completion）** | 交给 Tokio（见 D1） |
| 跨线程唤醒 I/O | `eventfd` | `kqueue` | **`PostQueuedCompletionStatus`** | 交给 Tokio |
| 定时器分辨率 | ns 级 | ns 级 | **默认约 15.6 ms** | 若做 Server MUST 显式提高；PoC 必须实测该分辨率对 p99 的影响 |
| 信号 | 完整 | 完整 | 极有限（无 SIGTERM 语义） | 优雅停机 MUST NOT 只依赖信号，MUST 提供显式 API；信号仅作额外触发 |
| 文件原子替换 | `os.replace` 原子 | `os.replace` 原子 | `os.replace` 在目标被占用时失败（杀软/索引器） | 加有限次重试并记日志 |
| 跨进程文件锁 | `flock` / `fcntl` | `flock` | `LockFileEx`（**语义不同**） | 本框架 MUST NOT 使用跨进程文件锁；线程锁足够 |
| 控制台编码 | UTF-8 | UTF-8 | **GBK（中文 Windows）** | 日志输出 MUST 显式指定 UTF-8 或不使用非 ASCII 字符 |

**层 3 · 现有 Python 代码的跨平台缺陷（已查实，均已登记并指定承接方）**

| 缺陷 | 位置 | 影响 | 承接方 |
|---|---|---|---|
| 文本模式 `open()` 未声明编码（16 处） | `core/params_factory.py:13,16,41` 等 | **跨平台配置静默损坏**：含中文的 UTF-8 配置在 `cp936` 下被读成 `璋冭瘯` 且不报错 | `fix-cross-platform-defects`（X2） |
| 日志含 emoji，控制台编码为 GBK | `conf/log_config.py:42`、`utils/structured_log.py:84` 及各日志调用点 | Windows 中文控制台抛 `UnicodeEncodeError`，**整行日志连同时间戳一起丢失** | `fix-cross-platform-defects`（X3） |
| 备份文件按秒命名 | `core/persistence_scheduler.py:180`、`workers/state_machine_work.py:150` | 同一秒内的多次备份相互覆盖（实测 3 次备份只产出 1 个文件） | `fix-cross-platform-defects`（X4） |
| `sys.argv[0].endswith("/src")` 判定失效 | `zoo_framework/__main__.py:65` | `zfc --worker` 永远写入 `./workers`。补测显示该条件对 Windows 的 `zfc.exe`、`C:\proj\src\__main__.py` 与 Linux 的 `/usr/local/bin/zfc` **全部为假**——**在所有平台上都是死条件**，非 Windows 特有 | `fix-cross-platform-defects`（X1） |
| `multiprocessing.Lock` 被用作线程锁 | `zoo_framework/utils/thread_safe_dict.py:1` | Windows 2063 ns vs Linux 181 ns（11.4x）；相对 `RLock` 为 13.3x vs 1.6x | `fix-worker-scheduling`（已覆盖，不重复登记） |
| CI 覆盖不均 | `.github/workflows/` | 仅 `tests.yml` 有三平台矩阵；`build.yml`/`quality.yml`/`docs.yml`/`release.yml` 全部 ubuntu-only。纯 Python 阶段无害，**引入 Rust 扩展后 `release.yml` 必须改为多平台** | `adopt-rust-core-impl`（P3） |

**明确不做的**：不为"统一平台差异"引入 `pywin32`、`uvloop`、`libuv` 等额外的平台专用依赖；不为 macOS 的 `kqueue` 或 Windows 的 IOCP 写任何自建封装。

## Risks / Trade-offs

- **[单平台测量导致结论平台偏差]**（**已实际发生一次**）→ 立项所用数据全部来自 Windows，补测 Linux 后发现 `multiprocessing.Lock` 相差 11.4x、进程启动相差 7.75x，两处结论需要修正。缓解：见 D0——profile 与边界成本测量 MUST 覆盖至少两个平台，所有结论 MUST 标注适用平台范围
- **[把 WSL2 当作原生 Linux]** → WSL2 的跨 vCPU 线程唤醒延迟是 Hyper-V 调度的伪影（实测 `submit().result()` 82 µs，高于 Windows 主机的 31.9 µs）。缓解：WSL 只用于验证机制性差异；涉及跨线程唤醒的绝对延迟 MUST 在 CI 的 `ubuntu-latest` 上取数
- **[产物矩阵失控]** → 完整的跨平台矩阵约 10 个产物，是长期维护成本的主要来源。缓解：见 D6 层 1——P3 先做 3 个核心产物，aarch64 与 musl 的支持须被实际需求证实后再增
- **[PoC 的合成基准不能代表真实负载，导致决策失真]** → 必须使用真实业务 trace 或可复现的真实场景，MUST NOT 只用空 Worker 的合成基准。测量脚本与其输入数据一并纳入 `bench/` 受版本控制
- **[Python 回调成本被低估]** → 在 PoC 中**直接测量**回调开销，而非引用公开基准数字。已有一项参考上界：ctypes 回调 0.33 µs/次（PyO3 应更低）
- **[测量受 `fix-worker-scheduling` 未完成污染]** → 该变更验收完成前不取基线；Proposal 已将其列为硬依赖
- **[构建链迁移破坏现有发布流程]** → P3 之前不动 `release.yml` 与 `pyproject.toml` 的构建后端；迁移与加速路径分开提交，任一步可独立回滚
- **[崩溃隔离方案在真实场景失效]**（panic 跨 FFI 边界未捕获、或在 Rust 持有 Python 引用时 panic） → PoC 必须覆盖 panic 用例并断言进程存活，这是 go 的必要条件
- **[失去纯 Python 的可读性与可热改属性]** → 由 D4 的可选加速路径缓解；纯 Python 实现永久可用，文档需明确两条路径的行为一致性要求
- **[本变更产出 no-go 结论被视为失败]** → 明确写入 Goals：no-go 是合法且低成本的成功产出，它避免的是数月无效投入

## Migration Plan

本变更自身的交付**不涉及产品代码迁移**，只交付 `bench/` 下的测量脚本与探针、以及决策文档。若决策为 go，迁移按 D5 的 P3 / P4 在后续变更中执行，其中：

- **回滚策略**：D4 的可选加速路径是回滚机制本身——移除扩展即可回到纯 Python，无需回退代码
- **灰度**：P3 阶段 Rust 核心默认不启用，通过配置项显式开启，先在一组真实负载上验证行为一致
- **行为一致性**：两条路径（纯 Python / Rust 加速）在同一组验收用例上 MUST 表现一致，该用例集在 `fix-worker-scheduling` 的回归测试基础上扩展

## Open Questions

### Open Question · go / no-go 的量化阈值 —— **已定稿并出结论**

**阈值定稿：15%**，并由实测给出交叉点。

| Worker 体时长中位数 | 当前占比 | Rust 化后占比（**实测**） | 判读 |
|---|---|---|---|
| 0.046 ms | 70.9% | 53.5% | 两者都远超阈值，Rust 也救不了 |
| 0.31 ms | 25.9% | 15.2% | 恰在阈值边界 |
| 2.7 ms | 4.3% | ~1.7% | 两者都在阈值内，不必要 |
| 10.3 ms | 2.1% | ~0.6% | 同上 |

**交叉点**：当前框架开销约 113 µs，交叉点在 Worker 体约 **640 µs**；Rust 化后
（开销约 51 µs）降到约 **290 µs**。即 Rust 化只在 Worker 体中位数落在 290–640 µs
这个窄带内时才改变结论，而该窄带内的收益上限也只有 **1.67x**。

**结论：no-go**（针对框架当前的形态）。完整的推理、成本对比与适用边界见
`bench/DECISION.md`。

**重大修正**：本设计早期估计 Rust 化后框架开销可降到 ~25 µs、整体 3–5x。实测为
**51–67 µs**，且不含任何调度语义。原因是这条链路里两次 `Python::with_gil` 获取与
主线程唤醒是主导成本，而它们不是调度实现问题——**瓶颈在 GIL，不在调度**。

### Open Question · Server 运行时是否纳入目标范围 —— **唯一未决项**

**状态**：结论已不依赖 Worker 体的粒度（见上表：任何粒度都不值得在当前的形态上引入
Rust）。剩下的是架构方向问题——是否要做**真正的 Server 运行时**。

**为什么它是另一种架构**：本次对照测的是"派发 Python 执行体并收回完成信号"这条链路，
GIL 在这里是瓶颈。而 Server 运行时是让 Rust **全程独立处理**连接与协议，Python 只在
请求到达时被调用一次——Rust 承担的是它能独立完成的工作，不经受本对照中的 GIL 往返。

**该架构的收益未被本次 PoC 测量**，需要单独的 PoC，且其对照对象应当是"Rust 处理 N 个
并发连接的吞吐 vs Python asyncio"，而不是"派发 Python 回调的延迟"。

### 两项未完成的前置，影响结论的强度

1. **四项纯 Python 优化至今未落地**（去 `gevent`、`ThreadSafeDict` 换锁、`FIFO` 换
   `deque`、默认启用资源池）。design 的 P1 把它们列为 `fix-worker-scheduling` 的一部分，
   但**该变更的 tasks 从未包含它们**——属任务表编写疏漏。它们的实测量级从 12x 到 800x，
   全部是纯 Python 可拿的收益。
2. **`concurrent.futures` 的记账占派发成本的绝大部分**：实测 `ThreadPoolExecutor.submit()`
   31.9 µs vs 裸 `queue.Queue` 直连 1.86 µs。换掉它是纯 Python 改动，成本远低于引入 Rust，
   而它触及的正是框架开销里占比最大的一段。

**因此**：`adopt-rust-core-impl`（P3）的合理前置不是"直接上 Rust"，而是**先做这两项纯
Python 优化并重测**。若它们就能把框架开销压到 60 µs 以内，Rust 的边际收益会进一步收窄，
届时阈值判断需要在新的基线上重做。
