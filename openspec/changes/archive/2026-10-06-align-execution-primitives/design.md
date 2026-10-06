# Design：执行原语对齐

## D1 事件投递用实例级 ThreadPoolExecutor（而非每轮建池）

`EventWorker._execute` 的 `g_queue` 每轮收集派发句柄、轮末 `joinall(timeout)`。对应改法：

- 执行器在 `EventWorker.__init__` 建一次（`max_workers` 由 `EventParams` 新键 `EVENT_EXECUTOR_WORKERS` 声明，默认 8），MUST NOT 在消费循环里 per-event 或 per-round 建池——建池成本会吃掉替换收益
- `gevent.spawn(reactor.execute, topic, content)` → `self._executor.submit(...)`；`gevent.joinall(g, timeout)` → `concurrent.futures.wait(fs, timeout=EventParams.EVENT_JOIN_TIMEOUT)`
- `_report_unfinished` 从 `g.ready()` 改 `f.done()`，日志文案保持"结果未被回收"的可观测语义
- **新增观测缺口补齐**：greenlet 里被吞的响应器异常，改经 `f.exception()`（仅对 `done()` 的 future 非阻塞检出）记日志。这是行为增强而非保持项，已由 `event-dispatch` delta 固化为条款
- 线程语义与 greenlet 的差异：greenlet 协作式、同进程单 OS 线程；改线程后响应器**真并发**执行，对既有响应器要求其自身线程安全——这与框架"多线程开发框架"的定位一致，不构成额外约束

## D2 状态 effect 用模块级共享 executor，同步等待语义保留

`_perform_effect` 每节点每次写入建池不现实，选**模块级懒建共享池**（`thread_name_prefix="zoo-state-effect"`）：

- `wait(fs, timeout=5)` 与 `gevent.joinall(timeout=5)` 逐项对应：effect 并发执行、写路径最长等 5 秒、超时后返回不阻塞
- **刻意保留**"写入同步等待 effect"：改为非阻塞投递会让"注册后写入即通知"的 `state-machine` 既有条款变成竞态语义，那是 #51/#32 线上当前的欠账，不在本变更掺入
- effect 异常经 `f.exception()` 记日志，不传播给写入方（与 greenlet 默认行为一致：`joinall` 不重抛）
- 共享池不主动 shutdown：解释器退出时由 `concurrent.futures.thread` 的 atexit 钩子回收；effect 是用户回调，框架不做强杀（greenlet 时代同样不强杀）

## D3 ThreadSafeDict 换锁连作用域一起换（每实例 RLock）

- `__init__` 增 `self._lock = threading.RLock()`，所有方法改用 `self._lock`；删除模块级 `_lock` 与 `multiprocessing` 导入
- 选 `RLock` 而非 `Lock`：防未来出现同实例嵌套调用（如 `pop` 内检 `has_key`）时自我死锁；无竞争时两者代价同级
- **作用域声明**（与 #50 / `scoped-container` 的"线程安全归属必须显式声明"合验）：锁随实例走——conftest 对 `reactor_map` / `_channel_map` 的"整实例替换"复位方式因此仍然成立，不需改动
- `ThreadSafeDict` 的键值仍是 Python 对象、读写的原子性边界不变（单次操作持锁），不引入复合操作原子性承诺

## D4 FIFO 换 deque，只动存储不动 API

- `BaseFIFO._fifo: deque[_T]`；`pop_value` 用 `popleft()`；`push_value` / `push_values` / `push_values_if_null` 的 `append` / `extend` / `in` 语义在 deque 上一致
- `DelayFIFO` 自己重置的 `self._fifo = []` 一并换 deque（它未走基类 `__init__`，两处真源必须同型）
- `SingleFIFO` 的 `index()` / 下标访问不改：deque 支持，且其 O(n) 与现状同级；该类的 `index_list` 类属性共享是**已知欠债**，归 #50，本变更不动
- 空队 `pop_value()` 返回 None 的边界语义 MUST 保持（事件消费路径在 `size()` 与取出之间依赖它兜并发空档）

## D5 依赖出树与 #34 的关系

- `pyproject.toml` 移除 `"gevent>=23.0.0"`；`requirements.txt` 移除 `gevent==23.9.1`；`uv lock` 重解后 greenlet / zope-event / zope-interface 出树
- **#34 的解决方式是"依赖消失"而非"升级 greenlet"**——issue 里留一条评论说明后关闭；不引入"要不要保留 gevent 为 extras"的中间态（框架定位是线程/进程并发，协程补丁路线已废）
- `mkdocs.yml` 顶部"必须带 --no-project（会触发 gevent 源码编译）"的注释随依赖出树更新

## D6 CI bench 与测量口径

- 新 workflow `.github/workflows/bench.yml`：`workflow_dispatch` + 每周 `schedule`；矩阵 `os: [ubuntu-latest, macos-latest, windows-latest]`（`fail-fast: false`）；跑 `measure_timer.py` / `profile_framework.py`；结果 JSON 已按 `<OS>-<arch>` 命名不互盖，上传为构件
- **不跑** `measure_boundary.py` 与 `compare_execution_models.py`：两者经 `load_probe()` 硬依赖已构建的 PyO3 探针（cargo/maturin），Rust 已 no-go，不值得为边界测量扩 CI 工具链
- 口径纪律沿用 `DECISION.md`：WSL2 数字不用于决策；跨平台数字不混排比较；测量波动不门禁功能开发（作业失败只报告不阻断）

## D7 zoo-bench free-threaded 目标（跨仓库）

- 前置纪律（该仓库 2026-10-04 的教训）：**先在本机 cp313t 装上 dev 框架、跑通 zoo-bench 全套用例，才改其 CI**
- `interpreters: ["3.13", "3.13t"]` 维度；3.13t **只测 `@dev`**——已发布版本声明 gevent 依赖，在 3.13t 上装不上，进矩阵必整列红；目标清单经 `zoo-bench frameworks | grep ' @ '` 筛选，不在 workflow 里写版本字面量
- `environment.py` 增 `gil_mode`（运行期 `sys._is_gil_enabled()` 实态，非仅认构建）；报告环境表展示 GIL 行（历史留档无此键时不补造）。**隔离不改 storage.py**：CLI 已有 `run --out` / `render --results`，3.13t 列留档走 `results/gil-free/`，天然不互盖；3.13t 列不参与跨版本对比页配对（相邻原则的例外，写在 matrix.yaml 头注）
- **决策门槛**：同机同负载 3.13 vs 3.13t，zoo 端到端中位收益 ≥15%（沿用 `DECISION.md` 阈值）才讨论"框架把 3.13t 列为支持目标"；否则转为长期观测列，不再投入

**本机 cp313t 实测结论（2026-10-06，任务 6.1）**：`cpython-3.13.14+freethreaded-windows` 上
`sys._is_gil_enabled()` 为 False；去 gevent 后的 dev 框架可直接安装，zoo-bench 全套
**325 passed / 2 skipped，与 3.13 同数**。两个边界（已回写进 CI 安装步骤）：

1. zoo-bench 声明不固定版本的 `zoo-framework` 依赖——harness 先装会从 PyPI 拉声明 gevent
   的 0.8.0 而失败，必须**框架（git 引用）先行**
2. 最新 numpy(2.5)/matplotlib(3.11)/pillow(12) 在 cp313t-Windows 无产物、退回源码构建失败；
   钉 `numpy<2.5` `matplotlib<3.11` `pillow<12` 后全绿

## Risks

| 风险 | 缓解 |
|---|---|
| 响应器从协作式切到真并发，隐含线程安全要求变化 | 框架本为多线程设计；`test_event.py` 补并发投递用例；CHANGELOG 标注 BREAKING（依赖出树）与本语义变化 |
| 模块级共享 effect executor 成为新的容器外载体 | 它是执行设施而非状态存储；在 #50 的归类清单中登记其归属声明 |
| `EventWorker` 池线程在 stop 时残留 | `BaseWorker` 停止路径不 join 在飞响应器与 greenlet 时代一致； executor 用 `shutdown(wait=False, cancel_futures=True)` 挂到 worker 停止钩子，行为不劣于现状 |
| CI 三平台首次跑通成本（脚本隐性平台假设） | 首版允许单平台失败继续其余（`fail-fast: false`），留档优先于整齐 |
