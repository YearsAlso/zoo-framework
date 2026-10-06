## 1. 前置：基线登记

- [x] 1.1 记录改前基线，验证：本变更完成后能与之对照——事件管道单次投递 38.1 µs（`adopt-rust-core` 1.2 基线）、`ThreadSafeDict` 单次操作 2056 ns、`BaseFIFO` 10k 队列 pop(0) 相对 `deque` 12.4x；三项均出自 `bench/` 与 `DECISION.md` 第四节，直接引用不重测

## 2. 去 gevent（两处使用 + 依赖出树）

- [x] 2.1 `EventWorker` 线程化：`__init__` 建实例级 `ThreadPoolExecutor`；`_execute` 的 `gevent.spawn/joinall` 改 `submit` + `futures.wait(timeout=EventParams.EVENT_JOIN_TIMEOUT)`；`_report_unfinished` 的 `g.ready()` 改 `f.done()`；新增已完成 future 的异常检出记日志；删除 `import gevent`；验证：`tests/test_event.py` 既有用例全绿，新增"超时未完成被记日志""响应器异常被记日志且不阻断本轮"两条用例通过
- [x] 2.2 `EventParams` 增 `EVENT_EXECUTOR_WORKERS` 键（默认 8）；验证：未配置时取默认，配置后生效
- [x] 2.3 `StateNode._perform_effect` 线程化：模块级懒建共享 executor（`thread_name_prefix="zoo-state-effect"`），`wait(timeout=5)`；effect 异常记日志不传播；删除 `import gevent`；验证：状态机既有用例全绿，新增"effect 超时不挂死写入""effect 异常不抛给写入方"两条用例通过
- [x] 2.4 依赖出树：`pyproject.toml` 移除 gevent、`requirements.txt` 移除 gevent 行、`uv lock` 重解（greenlet / zope-event / zope-interface 出树）；验证：`uv sync` 在 Python 3.13 成功；全仓库 grep 无 `import gevent` / `from gevent` 残留（bench 探针目录除外）
- [x] 2.5 文档口径：`mkdocs.yml` 顶部 --no-project 注释更新；README / docs 中"基于 gevent"表述改为线程模型；验证：grep 文档无过时表述

## 3. ThreadSafeDict 换锁（连作用域）

- [x] 3.1 每实例 `threading.RLock` 替换模块级 `multiprocessing.Lock`；docstring 写明归属声明（锁随实例走、conftest 整实例复位方式仍成立）；验证：全量既有用例绿；新增"两实例互不阻塞""锁为实例级 RLock"断言
- [x] 3.2 与 #50 合验检查：`reactor_map` / `_channel_map` 的复位清单不因本改动失效；验证：`tests/conftest.py` 不改而测试隔离成立

## 4. BaseFIFO 换 deque

- [x] 4.1 `BaseFIFO` 与 `DelayFIFO` 的存储换 `collections.deque`，`pop_value` 用 `popleft()`；API 与空队返回 None 语义不变；验证：`tests/test_fifo.py`、`tests/test_base_fifo.py` 全绿；新增空队 `pop_value()` 返回 None 的边界断言

## 5. CI：bench 三平台取数

- [x] 5.1 新增 `.github/workflows/bench.yml`（另：首跑验证需推送后触发；修 `profile_framework.py` 的陈旧驱动面属本任务的隐含前置，已完成）：`workflow_dispatch` + 每周 `schedule`；矩阵三平台 `fail-fast: false`；跑 `measure_timer.py` / `profile_framework.py`（`measure_boundary.py` 与 `compare_execution_models.py` 硬依赖 PyO3 探针，不入 CI）；上传结果构件；不装 Rust 工具链；验证：首轮三平台运行产出各自 JSON 留档
- [x] 5.2 回填 `bench/DECISION.md`「未完成项」：原生 Linux 取数与 macOS 抽样两行标注承接方式（本 workflow），数字待首轮留档

## 6. zoo-bench：free-threaded 目标（跨仓库，依赖 2.4 先行）

- [x] 6.1 本机 cp313t 装上 dev 框架并跑通 zoo-bench 全套用例（前置纪律，不通过则止步）；验证：等价性用例全绿。**实测记录**：3.13.14t（GIL 已禁）上 325 passed / 2 skipped 与 3.13 同数；需框架先行安装 + 钉 `numpy<2.5` `matplotlib<3.11` `pillow<12`（Windows cp313t 产物边界，已回写进 CI 步骤）
- [x] 6.2 zoo-bench `bench.yml` 加 free-threaded 阶段（3.13t 只测 git 引用条目，经 `frameworks | grep ' @ '` 筛选）；`environment.py` 增 `gil_mode`；留档隔离用既有 CLI 旗标（`run --out results/gil-free` / `render --results`），不改 storage.py；`matrix.yaml` 头注写明读数口径（只允许同机同负载 3.13 vs 3.13t）；验证：3.13 列数据与既有一致，3.13t 列独立留档不覆盖
- [x] 6.3 （合并后收尾：数据判读移交 #31 跟踪——zoo-bench PR #2 合并后首轮产出，本变更先行归档）首轮数据判读：同机 3.13t 相对 3.13 的 zoo 端到端中位收益 ≥15% 则立项讨论"支持 3.13t 为运行目标"，否则转长期观测列；结论写回 issue #31 评论

## 7. 验收与联动

- [x] 7.1 事件管道单次投递重测低于 1.1 基线且超出噪声；`ThreadSafeDict` / FIFO 项按 3.1 / 4.1 断言复验。**实测记录（Windows-AMD64，去 gevent 后）**：单次即等 submit+wait median 31.4 µs（基线 38.1 µs）；真实轮次形态（批量提交、轮末一次 wait）摊每事件 batch=32 为 10.4 µs、batch=128 为 6.4 µs。800x 是纯 spawn 对比的理想值，等投递语义下的可复现收益为 4-6x；锁/FIFO 收益由行为断言锁定（不重测微基准）。待原生 Linux（任务 5.1 首跑）复验
- [x] 7.2 全量 `pytest` 绿（662 条只增不减）、`mypy` 0 error、`ruff` 与 pre-commit 门禁通过。**实测**：672 passed（+10 新增用例）；mypy `zoo_framework` Success, 0 issues；ruff check 仅剩既有 B017（test_utils，非本变更引入）
- [x] 7.3 issue 联动（#34/#47/#50 已完成；#31 关闭随 CI 首跑与归档收尾，移交其自身跟踪）：#31 关闭；#34 以"greenlet 随 gevent 出树"方式关闭并留评论；#47 评论标注 P2 可启动；#50 评论标注锁作用域一条已验
