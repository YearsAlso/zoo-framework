# 性能基准说明 / Benchmark notes

[English](#en) | [中文](#zh)

## 两个仓库的分工（先读这段）

本仓库里有两处与性能测量相关的东西，**定位不同、寿命不同，不要混用**：

| | `bench/`（本仓库） | [`zoo-bench`](https://github.com/YearsAlso/zoo-bench)（独立仓库） |
|---|---|---|
| 是什么 | `adopt-rust-core` 那次可行性论证的**一次性证据** | **长期维护**的基准 harness |
| 回答什么 | "要不要把派发核心换成 Rust？" → **no-go** | "相对各对照方案，本框架快不快、在哪些档位输" |
| 寿命 | 结论已归档，**只读** | 逐版本发布，持续更新 |
| 数据 | Windows 本机实测（Linux 数字因 WSL2 不可用） | 原生 Linux CI（`ubuntu-latest`），公开原始数据 |
| 线上 | — | [线上报告](https://yearsalso.github.io/zoo-bench/) |

**要引用性能数字，用 zoo-bench 的报告**（它是维护中的、可复现的、也公开了不利档位的那一份）；
`bench/` 的价值在于"为什么否掉了 Rust"这个决策本身。

下文是 `bench/` 这份测量的**导读**。
权威依据是 [`bench/DECISION.md`](https://github.com/YearsAlso/zoo-framework/blob/dev/bench/DECISION.md)
（结论与依据）与 [`bench/README.md`](https://github.com/YearsAlso/zoo-framework/blob/dev/bench/README.md)
（复现步骤与适用边界）；本文只做提炼，如果两者不一致，以那两份为准。

> 上述链接使用绝对地址，因为它们指向 `docs/` 之外的仓库文件——相对路径在文档站上会失效。
> 固定到 `dev` 分支是因为 `bench/` 目前只存在于 `dev`。


---

<a name="english"></a>
## 🇬🇧 English {#en}

### What was measured, and why

`bench/` is a feasibility study for one question: **is it worth replacing the framework's
dispatch core with Rust?** It is measurement and decision material only — nothing in it
changes the runtime behaviour of `zoo_framework/`.

**Verdict: no-go**, for the framework's current shape (dispatch a Python callable, run it,
collect the completion signal). Measured end-to-end speedups cap at **1.67x**, with a
typical range of 1.0–1.2x — not enough to justify a maturin build chain, a 6+ platform
wheel matrix, a Rust toolchain in CI, mixed-stack debugging, and losing the "readable
source, hot-editable, pip-installable" property.

### The two decisive numbers

**1. Framework overhead is 94–220 µs per task** (Windows, Python 3.13, body duration
instrumented within the same run):

| Tier | Worker body | End-to-end | Framework overhead | Share |
|---|---|---|---|---|
| cpu-1x | 0.039 ms | 0.133 ms | 0.094 ms | **70.76%** |
| cpu-10x | 0.289 ms | 0.391 ms | 0.102 ms | **26.12%** |
| cpu-100x | 2.734 ms | 2.858 ms | 0.124 ms | **4.34%** |
| io-10ms | 10.332 ms | 10.551 ms | 0.219 ms | **2.08%** |

Overhead is roughly constant; its *share* falls as the body gets longer.

**2. The PyO3 boundary crossing is not the cost.** A Python→Rust empty round trip is
**28.9 ns** on Windows (23.9 ns on Linux) — essentially the same as a pure-Python empty
call (27.4 ns). The design had cited 0.33 µs, taken from a ctypes upper bound: an ~11x
overestimate.

### Why Rust does not help here

A minimal Tokio dispatcher (`pyo3_probe.RustDispatcher`) was compared against the
framework's dispatch path on the same machine, same workload, same wakeup mechanism.
The Rust side implements **no scheduling semantics** — no timeout circuit-breaker, no
in-flight table, no result aggregation — so it measures a **lower bound**.

| Tier | Python end-to-end | Rust end-to-end | Speedup |
|---|---|---|---|
| cpu-1x (~46 µs body) | 0.1589 ms | 0.0950 ms | **1.67x** |
| cpu-10x (~0.31 ms body) | 0.4159 ms | 0.3417 ms | **1.22x** |
| io-10ms (~10.3 ms body) | 10.5597 ms | 10.4958 ms | **1.01x** |

Rust's own overhead is **51–67 µs** and contains no scheduling semantics — real timeout
checks, in-flight maintenance and result aggregation would push it higher. The reason it
does not reach the anticipated ~25 µs is that the dominant cost in this path is **two
`Python::with_gil` acquisitions (body, then completion callback) plus the main-thread
wakeup** — and those are not a scheduler-implementation problem. **The bottleneck is the
GIL, not the scheduler.**

Against the project's 15%-overhead threshold, Rust only flips the verdict inside a narrow
band: the crossover sits at roughly a **290–640 µs** median task duration, and even there
the ceiling is 1.67x.

### The exception this PoC did not measure

A true **Server runtime** (Rust owns connections and protocol; Python is invoked once per
request) is a *different architecture* — it never pays the GIL round trip that dominates
this comparison. That would need its own PoC measuring concurrent-connection throughput
rather than dispatch latency. See the closing question in `bench/DECISION.md`.

### Do these first

Four **pure-Python** optimizations were measured at **12x–800x**, dwarfing Rust's 1.67x:

| Optimization | Measured gap |
|---|---|
| Drop `gevent` from the event pipeline | 38.1 µs vs 47.5 ns (**800x**) |
| `ThreadSafeDict`: `multiprocessing.Lock` → `threading.RLock` | 2056 ns vs 155 ns (**13x**) |
| `BaseFIFO` → `deque` | 12.4x with 10k queued |
| Enable the worker resource pool by default | 222 µs vs 13.5 µs (**16x**) |

`ThreadPoolExecutor`'s own bookkeeping (31.9 µs) against a bare `queue.Queue` (1.86 µs)
points at the same conclusion: the largest single share of dispatch cost is not the
scheduler.

These four were argued in the design but **never appeared in any change's task list**.
Their ownership was settled on 2026-09-27 and recorded in `bench/DECISION.md` — "enable
the resource pool by default" belongs to `scheduler-model-seam`; the other three to the
pending change `align-execution-primitives`. They remain **not done**.

### Three hard constraints on reading the data

1. **The Linux framework-overhead numbers are unusable.** WSL2's hypervisor inflates
   cross-thread wakeup (~3x), so framework overhead reads 328–432 µs. Native Linux
   sampling needs CI's `ubuntu-latest`.
2. **The workload is a stand-in, not a real trace.** `bench/workload.py` approximates a
   realistic shape (JSON encode/decode + string processing + optional short I/O); its
   applicability limits are stated in the file header. No real sample exists in the repo.
3. **Body duration must be instrumented within the same run.** Subtracting a separately
   measured body cost introduces systematic bias — the first version of
   `profile_framework.py` overestimated overhead by 2x this way.

### Reproducing

Requires Python 3.13, the project's runtime dependencies, a Rust toolchain (boundary
measurement only) and `maturin`.

```bash
# Build the probe (boundary measurement only); cargo also works
cd bench/pyo3_probe && maturin build --release -i "<absolute path to a 3.13 interpreter>"

PY bench/measure_boundary.py      # -> results/boundary_<platform>.json
PY bench/measure_timer.py         # -> results/timer_resolution_<platform>.json
PY bench/profile_framework.py     # -> results/framework_overhead_<platform>.json
```

> Use an explicit 3.13 interpreter. The `venv/` directory in this repo is Python 3.9 and
> cannot import the package; `.venv/` is the 3.13 one.

Crash isolation (design D3) is verified by the probe's three panic paths —
`pyo3_probe.panics()`, `catches_panic()`, `panics_holding_python_ref(f)` — which confirm
a Rust panic does not abort the process. `bench/pyo3_probe/target/` is build output and is
gitignored.

---

<a name="中文"></a>
## 🇨🇳 中文 {#zh}

### 测了什么，为什么测

`bench/` 是一次可行性论证，回答一个问题：**是否值得把框架的派发核心换成 Rust？**
它只是测量与决策材料 —— `zoo_framework/` 的运行时行为不因它而改变。

**结论：no-go**，针对框架当前的形态（派发一段 Python 执行体、执行、收回完成信号）。
实测端到端加速比上限 **1.67x**，典型档位 1.0–1.2x —— 不足以支撑引入 Rust 的成本：
maturin 构建链、6+ 平台 wheel 矩阵、CI 增加 Rust 工具链、混合堆栈调试，以及失去
「可读源码、可热改、pip 直接装」这些属性。

### 两个决定性数字

**1. 框架自身开销为每任务 94–220 µs**（Windows / Python 3.13，执行体耗时在同一次运行内
埋点测得）：

| 档位 | Worker 体 | 端到端 | 框架开销 | 占比 |
|---|---|---|---|---|
| cpu-1x | 0.039 ms | 0.133 ms | 0.094 ms | **70.76%** |
| cpu-10x | 0.289 ms | 0.391 ms | 0.102 ms | **26.12%** |
| cpu-100x | 2.734 ms | 2.858 ms | 0.124 ms | **4.34%** |
| io-10ms | 10.332 ms | 10.551 ms | 0.219 ms | **2.08%** |

开销基本恒定；**占比**随执行体变长而下降。

**2. PyO3 边界穿越不是成本所在。** Python→Rust 空调用往返为 **28.9 ns**
（Linux 23.9 ns），与纯 Python 空调用（27.4 ns）几乎相同。design 原引用的 0.33 µs 取自
ctypes 上界，**高估了约 11 倍**。

### 为什么 Rust 在这里帮不上忙

用最小 Tokio 调度器（`pyo3_probe.RustDispatcher`）与框架当前的调度路径做同机对照：同一份
执行体、同一份输入、同一套唤醒机制。Rust 侧**不实现**任何调度语义 —— 无超时熔断、无在飞表、
无结果聚合 —— 因此测的是这条链路的**下界**。

| 档位 | Python 端到端 | Rust 端到端 | 加速比 |
|---|---|---|---|
| cpu-1x（执行体 ~46 µs） | 0.1589 ms | 0.0950 ms | **1.67x** |
| cpu-10x（执行体 ~0.31 ms） | 0.4159 ms | 0.3417 ms | **1.22x** |
| io-10ms（执行体 ~10.3 ms） | 10.5597 ms | 10.4958 ms | **1.01x** |

Rust 侧自身开销是 **51–67 µs**，且不含任何调度语义 —— 加上真实的超时判定、在飞表维护与
结果聚合后只会更高。它没能降到预期的 ~25 µs，原因是这条链路的主导成本是**两次
`Python::with_gil` 获取（执行体一次、完成回调一次）加主线程唤醒**，而它们**不是调度实现
问题**。**瓶颈在 GIL，不在调度。**

对照本项目 15% 开销阈值：Rust 化只在很窄的区间里能翻转结论 —— 交叉点大致落在 Worker 体
中位数 **290–640 µs**，且在那个区间里收益上限也只有 1.67x。

### 本次 PoC 没有测的那个例外

真正的 **Server 运行时**（Rust 全程处理连接与协议，Python 只在请求到达时被调用一次）是
**另一种架构** —— 它不经受本对照中主导成本的 GIL 往返。那需要单独的 PoC，测的应该是
「Rust 处理 N 个并发连接的吞吐」，而不是「派发 Python 回调的延迟」。见 `bench/DECISION.md`
结尾待你确定的问题。

### 在上 Rust 之前，先做这些

四项**纯 Python** 优化实测 **12x–800x**，量级远超 Rust 的 1.67x：

| 优化项 | 实测差距 |
|---|---|
| 事件管道去 `gevent` | 38.1 µs vs 47.5 ns（**800x**） |
| `ThreadSafeDict` 换 `threading.RLock` | 2056 ns vs 155 ns（**13x**） |
| `BaseFIFO` 换 `deque` | 队列 10k 时 12.4x |
| 默认启用资源池 | 222 µs vs 13.5 µs（**16x**） |

`ThreadPoolExecutor` 自身的记账（31.9 µs）对比裸 `queue.Queue`（1.86 µs）指向同一结论：
派发成本里占比最大的一段不是调度器。

这四项在 design 中被论证过，却**从未出现在任何变更的任务表里**。归属已于 2026-09-27 裁定
并记录在 `bench/DECISION.md`：「默认启用资源池」归 `scheduler-model-seam`，其余三项归待立
变更 `align-execution-primitives`。这四项**至今未完成**。

### 数据解读的三条硬约束

1. **框架开销的 Linux 数字不可用。** WSL2 的 Hypervisor 放大跨线程唤醒（约 3 倍），框架开销
   因此虚高到 328–432 µs。原生 Linux 取数需要 CI 的 `ubuntu-latest`。
2. **负载是替身，不是真实 trace。** `bench/workload.py` 用一个形状接近真实业务的执行体近似
   （JSON 编解码 + 字符串处理 + 可选短 I/O）；适用边界写在文件头。仓库内没有真实样本。
3. **执行体耗时必须在同一次运行内埋点。** 用另一次单独测量的结果做减法会引入系统性偏差 ——
   `profile_framework.py` 的第一版就因此把开销高估了一倍。

### 复现

需要 Python 3.13、项目运行时依赖、Rust 工具链（仅边界测量需要）与 `maturin`。

```bash
# 构建探针（仅边界测量需要）；没有 maturin 时 cargo 也可以
cd bench/pyo3_probe && maturin build --release -i "<3.13 解释器的绝对路径>"

PY bench/measure_boundary.py      # -> results/boundary_<platform>.json
PY bench/measure_timer.py         # -> results/timer_resolution_<platform>.json
PY bench/profile_framework.py     # -> results/framework_overhead_<platform>.json
```

> 请使用明确的 3.13 解释器。仓库里的 `venv/` 是 Python 3.9 且无法导入本包；
> `.venv/` 才是 3.13。

崩溃隔离（design D3）由探针的三条 panic 路径验证 —— `pyo3_probe.panics()`、
`catches_panic()`、`panics_holding_python_ref(f)` —— 确认 Rust panic 不会 abort 进程。
`bench/pyo3_probe/target/` 是构建产物，已 gitignore。
