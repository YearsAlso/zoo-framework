# bench —— 测量与决策（adopt-rust-core）

**这些脚本不进入产品代码。** `zoo_framework/` 的运行时行为不因本目录而改变。

## 结论在哪

- **决策文档**：[`DECISION.md`](DECISION.md)
- **原始数据**：[`results/`](results/)（每平台一个 JSON，外加 `SUMMARY.json`）

## 目录

```
bench/
├── DECISION.md             go / no-go 结论与依据
├── README.md               本文件
├── workload.py             代表性业务负载（真实 trace 的替身，适用边界见文件头）
├── measure_boundary.py     PyO3 边界成本实测（任务组 3）
├── measure_timer.py        平台定时器分辨率实测（任务 3.6）
├── profile_framework.py    框架开销占比实测（任务 6.1 / 6.2）
├── results/                测量结果
└── pyo3_probe/             PyO3 探针扩展（Rust）
```

## 复现步骤

### 前置

- Python 3.13
- framework 的运行时依赖：`click jinja2 pyyaml python-dotenv typing-extensions gevent`
- Rust 工具链（仅边界成本测量需要）：`rustup`，stable
- `maturin`：`uv tool install maturin`（或 `cargo install maturin`）

> **注意本机的解释器**：仓库内 `venv/` 是 Python 3.9 且无法导入本包；`.venv/` 才是 3.13。
> 下文用 `PY` 指代一个可用的 3.13 解释器。

### 1. 构建探针（仅边界成本测量需要）

```bash
cd bench/pyo3_probe
maturin build --release -i "<PY 的绝对路径>"
```

没有 maturin 时也可以直接用 cargo（`measure_boundary.py` 会自动回退到该产物）：

```bash
cd bench/pyo3_probe && cargo build --release
```

### 2. 运行测量

```bash
PY bench/measure_boundary.py      # 边界成本    -> results/boundary_<platform>.json
PY bench/measure_timer.py         # 定时器分辨率 -> results/timer_resolution_<platform>.json
PY bench/profile_framework.py     # 框架开销占比 -> results/framework_overhead_<platform>.json
```

### 3. 崩溃隔离验证（design D3）

探针内含三条 panic 路径，用于验证"Rust panic 不得 abort 进程"：

```python
import pyo3_probe
pyo3_probe.panics()                      # 未兜住的 panic -> PanicException，进程存活
pyo3_probe.catches_panic()               # catch_unwind 兜住 -> RuntimeError
pyo3_probe.panics_holding_python_ref(f)  # 持有 Python 引用时 panic -> 进程存活，后续调用正常
```

三条路径在 Windows 与 Linux 上均已验证通过。

## 数据解读的三条硬约束

1. **框架开销的 Linux 数字不可用**。WSL2 的跨线程唤醒被 Hypervisor 放大（实测
   `ThreadPoolExecutor` 往返 82 µs vs Windows 31.9 µs），框架开销因此虚高约 3 倍。
   原生 Linux 取数需要 CI 的 `ubuntu-latest`。
2. **负载是替身，不是真实 trace**。`workload.py` 用一个形状接近真实业务的执行体
   （JSON 编解码 + 字符串处理 + 可选短 I/O）近似。结论的适用边界写在文件头。
3. **执行体耗时必须在同一次运行内埋点**。用另一次单独测量的结果做减法会引入系统性
   偏差——`profile_framework.py` 的第一版就因此把开销高估了一倍。
