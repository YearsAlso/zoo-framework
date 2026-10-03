# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Zoo Framework (`zoo-framework` on PyPI) is a multi-threaded Python framework built on a **zoo metaphor** that maps onto the concurrency primitives:

| Metaphor | Component | Role |
|---|---|---|
| 🦁 Animal | Worker | Task execution unit |
| 🏠 Cage | `ScopedContainer` | Per-scope holder of shared instances (process / session / prototype) |
| 👨🌾 Zookeeper | `Master` | Framework lifecycle manager |
| 🍎 Food | Event | Inter-worker message |
| 🥘 Feeder queue | FIFO / EventChannel | Ordered event queue |

Requires **Python 3.13+** (`requires-python = ">=3.13"` in `pyproject.toml`, hatchling backend, wheel packages `zoo_framework`). Docs and CI also say 3.8+ in places — that is stale, and the code uses `X | None` syntax that will not import below 3.10, let alone 3.9.

Comments, docstrings, docs and config comments in this repo are written in Chinese, and code docstrings use Google-style sections (`Args:` / `Returns:`). Match that when editing existing files. Roadmap/plan documents label work items `P0`/`P1`/`P2` by priority — that vocabulary appears in module docstrings too.

## Commands

```bash
# Setup (uv.lock is committed; plain pip also works)
uv sync                                  # or: pip install -e ".[dev]"
pre-commit install

# Tests (testpaths = tests, configured in pyproject.toml)
pytest
pytest tests/test_worker.py::TestBaseWorker::test_worker_execute   # single test
pytest -m "not slow"
pytest --cov=zoo_framework --cov-report=term-missing

# Quality gates
ruff check zoo_framework --fix
ruff format zoo_framework
mypy zoo_framework
bandit -r zoo_framework -c .bandit.yaml
pre-commit run --all-files

# CLI scaffolding (entry point zfc / zoo)
zfc --create <app_name>     # scaffold a project dir with src/, config.json, templates
zfc --worker <name>         # add <name>_worker.py to ./workers or ./src/workers

# Build / release
python -m build
```

Design docs live in `docs/` (`ARCHITECTURE.md`, `DEVELOPMENT.md`, `OPTIMIZATION_PLAN.md`, `ROADMAP.md`). Development is also driven by **OpenSpec** (`openspec/`): `openspec/specs/<capability>/spec.md` are the authoritative behavior specs, `openspec/changes/<id>/` holds in-flight changes (proposal → design → spec deltas → tasks), and completed ones move to `openspec/changes/archive/<date>-<id>/`. `openspec validate --strict` gates each change; `openspec/config.yaml` pins artifacts to zh-CN while structural headings and SHALL/MUST keywords stay English.

Note: a Python 3.9 `venv/` sits in the working tree (no longer tracked — it was dropped from the index — and still not covered by `.gitignore`), and bare `python` on this machine resolves to it. It cannot import the package. Use `uv run`, `.venv/Scripts/python.exe`, or another explicit 3.13 interpreter.

## Architecture

### Package layout by concern

- `zoo_framework/core/` — `master.py` (lifecycle + SVM), `worker_registry.py`, `params_factory.py`, `params_path.py`, `persistence_scheduler.py`, `zoo_thread.py`, and the `aop/` + `waiter/` subpackages.
- `zoo_framework/workers/` — `base_worker.py`, `event_worker.py`, `state_machine_work.py`, `async_worker.py`, plus result/props/register value objects.
- `zoo_framework/event/`, `fifo/`, `reactor/` — the event pipeline (channel registry → FIFO queue → reactor dispatch).
- `zoo_framework/statemachine/` — `StateMachineManager` → `StateScope` → pluggable `StateIndex`.
- `zoo_framework/params/` — configuration schema classes (one per concern), plus `constant/`, `utils/`, `conf/`, `templates/`, `plugin/`.

### Boot sequence (`Master.__init__` → `Master.run`)

1. `MasterConfig(config_path=...)` -> `ParamsFactory(path)` loads `config.json` into `ParamsFactory.config_params` (a class attribute, i.e. process-global), then resolves the `_exports` list into additional `<name>.json` files.
2. `_load_config()` runs every callable registered in `config_funcs` (the `@configure(topic)` registry) — currently the log configurator.
3. `_register_default_workers()` registers `StateMachineWorker` and `EventWorker` **as classes** in the global `WorkerRegistry` (a module-level singleton from `get_worker_registry()`; it is never reset between `Master` instances).
4. `SVMWorker` is created and started on a daemon thread; it holds per-worker metrics and flips status to `warning`/`unhealthy` on error rate.
5. `_create_waiter()` builds a `BaseWaiter` via `WaiterFactory.get_waiter()` — keyed by **scheduling-model name** (`worker:mode`, derived from `worker:pool:enable` when unset), not by the legacy `simple`/`stable`/`safe` policy names. Each `BaseWaiter` composes a `WorkerDispatchCore` (model-agnostic bookkeeping) with a `SchedulerModel` (`ThreadPerTaskModel` / `ThreadPoolModel`).
6. `run()` creates `asyncio` task `perform()`, which loops `waiter.execute_service()` every second until `KeyboardInterrupt`, then `shutdown()`.

### Wiring is decorator-driven, and those decorators are process-global

- **`@cage` no longer exists** (deleted in `scoped-container`, commit `89f32d6`). It used to replace the class with a factory function returning a cached singleton keyed by *class name* in a module-global `ThreadSafeDict` — which broke `issubclass`/`isinstance` (that caused a P0) and let two same-named classes silently alias each other. Framework-internal process-level sharing now goes through `core/container/` (`ScopedContainer`) via the non-class-replacing decorator `process_scoped(thread_safety=...)` in `core/container/registry.py`; the 8 ex-caged sites are `EventReactorManager`, `EventChannelManager`, `EventChannelRegister`, `EventProvider`, `EventRegister`, `WaiterResultReactor`, `StateMachineManager`, `StateNodeIndexFactory`. `X()` still returns the process-level instance (so call sites were unchanged), but the class stays a real class, the key is module + qualname, and "process-level" is a declaration that is `reset()`-able and `replace()`-able. **A guard test (`tests/test_no_class_replacement.py`) now fails if any module-level `class` is replaced by a decorator**, scanned across the whole framework. Note `tests/conftest.py`'s isolation fixture resets the container (`framework_container().reset()`) plus the class-level registries (`reactor_map`, `_channel_map`) plus things *outside* the container (`WorkerRegistry`'s caches, channel config) — three distinct carriers, and the container only covers the first.
- `@params` (`core/aop/params.py`) rewrites each `ParamsPath` class attribute into the resolved literal value, so the class ends up holding a plain value, not a handle. `ParamsPath(value, default, aliases)` resolves in the order **primary path → `aliases` → `default`**; `_resolve` tests `is not None`, so a configured falsy value (`False`/`0`/`""`) is honoured rather than treated as missing. `aliases` absorbs historical key names — `params/worker_params.py` uses it for `worker:pool:enable` vs the `worker:pool:enabled` that `zfc --create` used to emit, a mismatch that previously made the setting be **silently ignored**. **Resolution happens once, at first import of that params module, cached by `_cache_key(cls)` = module + qualname** (it used to key on the bare `cls.__name__`, which made two same-named params classes collide — fixed in `e041040`; the same anti-pattern `@cage` had). `zoo_framework/params` is imported lazily (inside `Master._create_waiter`, `BaseWaiter.__init__`, `StateMachineWorker`) precisely so that `ParamsFactory` has read `config.json` first. Importing a params class before constructing `Master` (or calling `ParamsFactory(path)`) freezes the defaults instead — `ParamsFactory()` with a missing path returns early and silently leaves `config_params` empty.
- `@worker(count=n)` registers instances into the legacy `WorkerRegister` (`worker_register` in `core/aop/worker.py`), separate from the newer `WorkerRegistry`. Both exist; `Master` uses `WorkerRegistry`.
- `@event(topic, channel=...)` (`core/aop/event.py`) builds an `EventReactor` around the function and registers it into the channel manager at import time.
- The config path defaults to `./config.json`, relative to the working directory.

### Worker execution path

`Waiter.execute_service()` iterates workers, requeues the ones whose `is_loop` is truthy, and dispatches un-tracked workers to either a `ThreadPoolExecutor` (when `worker.pool.enable` is true) or a bare `threading.Thread`. `BaseWaiter.worker_running` calls `worker.run()`; `BaseWorker.run()` wraps `_execute()` with `_destroy_result`, `_on_error`/`_on_done` hooks, sleeps `delay_time`, and returns a `WorkerResult(topic, content, cls_name)`.

`WorkerResult` is only handed to `EventReactorManager().dispatch(...)` through `Future.add_done_callback` in **thread-pool mode**; in plain thread mode the result is discarded, so a `WaiterResultReactor` on topic `"waiter"` never fires. Also note `BaseWorker.is_loop` is defined as a *method* while callers read it as an attribute (`if worker.is_loop:`) — always truthy unless a subclass shadows it with an instance attribute (`EventWorker` and `StateMachineWorker` both do).

### Event pipeline

`@event` / `EventChannelManager.refresh_channel` binds a reactor to a `(channel, topic)` pair → `EventChannelRegister` lazily creates `EventChannel`s (each owning an `EventFIFO`) → producers push `EventNode`s → the framework's own `EventWorker._execute` drains every channel, drops expired nodes, requeues nodes that still have retries, and runs the remaining reactors concurrently with `gevent.spawn` + `gevent.joinall` under `EventParams.EVENT_JOIN_TIMEOUT`.

`EventNode` carries `response_mechanism` (1 = first reactor, 2 = all by priority, 3 = all, 4 = named reactor) and a weighted priority: `EventPriorityCalculator.calculate` adds an age-based bonus so low-priority events do not starve. Note that `EventWorker` calls `reactor.perform(...)`, but `EventReactor` only defines `execute(topic, content)` — the two halves of this pipeline do not line up.

### State machine persistence

`StateMachineManager` holds `StateScope`s, each backed by a `StateIndex` from `StateIndexFactory` (default `ThreadSafeDict`-backed). `StateMachineWorker` (loop, 5s) loads the pickle at `stateMachine:picklePath` on first pass and saves on subsequent passes; `PersistenceScheduler`/`PicklePersistenceStrategy` provide the same atomic-write + checksum + rolling-backup logic as a reusable component. Writes go to a `.tmp` file and are `os.replace`d; up to 5 backups are kept in a sibling `backups/` directory.

### Extension points

`zoo_framework/plugin/__init__.py` holds the whole plugin system in one module: `Plugin` (ABC with `initialize(context)`/`destroy()`), `PluginManager` (register/load/dependency ordering/`load_from_path`), `WorkerDelayManager` plus `FixedDelay`/`ExponentialDelay`/`AdaptiveDelay` strategies, and module-level helpers `get_plugin_manager()`, `register_plugin()`, `load_plugins()`.

## `bench/` — Rust feasibility PoC (verdict: **no-go**)

`bench/` is a **measurement and decision** area belonging to the `adopt-rust-core` change. It is not product code: nothing there changes `zoo_framework/` runtime behavior.

```
bench/
├── DECISION.md                  go/no-go verdict, the numbers, and the open items
├── workload.py                  representative load (a stand-in, not a real trace)
├── measure_boundary.py          Python<->Rust call cost
├── measure_timer.py             platform timer resolution
├── profile_framework.py         framework overhead as a share of end-to-end latency
├── compare_execution_models.py  Python dispatch path vs Rust (Tokio) dispatch path
├── results/*.json               one JSON per platform, plus SUMMARY.json
└── pyo3_probe/                  the Rust probe (PyO3 0.23 + tokio 1, cdylib)
```

**The Rust probe is deliberately minimal** — 8 `#[pyfunction]`s (Python→Rust round trip, Rust→Python callback holding the GIL, `allow_threads` round trip, fine- vs coarse-grained crossing counts, three panic paths) plus one `#[pyclass]` `RustDispatcher` wrapping a multi-thread Tokio runtime. `submit` crosses the boundary twice per task (`Python::with_gil` for the body, again for the completion callback) and **implements no scheduling semantics** — no timeout/circuit-breaker, no in-flight table, no result aggregation. It therefore measures a **lower bound**; a real Rust scheduler would be slower than the 51–67 µs it reports.

**Verdict: no-go** for the framework's current shape (dispatch a Python callable, run it, collect the completion signal). Measured end-to-end speedups: 1.67x (cpu-1x), 1.22x (cpu-10x), 1.01x (io-10ms). **The bottleneck is the GIL and cross-thread wakeup, not the scheduler** — the boundary crossing itself costs only 28.9 ns (the design had cited 0.33 µs, an ~11x overestimate taken from a ctypes upper bound). Rust only flips the 15%-overhead threshold inside a narrow ~290–640 µs band of median task duration, and even there caps at 1.67x.

Two findings in `DECISION.md` matter more than the Rust question itself:

- **Four pure-Python optimizations measure 12x–800x**, dwarfing Rust's 1.67x: dropping `gevent` from the event pipeline (38.1 µs → 47.5 ns), `ThreadSafeDict`'s `multiprocessing.Lock` → `threading.RLock` (2056 → 155 ns), `BaseFIFO` → `deque` (12.4x at 10k queued), and enabling the worker resource pool by default (222 µs → 13.5 µs). `ThreadPoolExecutor`'s own bookkeeping is 31.9 µs vs 1.86 µs for a bare `queue.Queue`.
- Those four were **never allocated to any change's task list** — they were argued in the design but absent from `fix-worker-scheduling`'s tasks. Recorded as an open item in `DECISION.md` rather than silently dropped. Before reaching for Rust, do these first and re-measure.

**Reproducing** needs Python 3.13, a Rust toolchain, and `maturin` (`cargo build --release` alone also works — `measure_boundary.py` falls back to that artifact). Then `PY bench/measure_boundary.py`, `measure_timer.py`, `profile_framework.py`. `pyo3_probe/target/` is build output and is gitignored.

**Three hard constraints on reading the data** (stated in `bench/README.md`):

1. The Linux *framework-overhead* numbers are unusable — WSL2's hypervisor inflates cross-thread wakeup ~3x. Native Linux sampling needs CI's `ubuntu-latest`.
2. `workload.py` is a stand-in with a realistic shape, not a real trace.
3. Body duration must be instrumented **within the same run**; subtracting a separately measured body cost once overestimated overhead by 2x.

**One exception is explicitly unmeasured**: a true *Server runtime* (Rust owns connections and protocol, Python invoked once per request) is a different architecture that never pays the GIL round trip this comparison is dominated by. It would need its own PoC measuring concurrent-connection throughput rather than dispatch latency. `DECISION.md` ends by asking which of the two this project is actually building — that answer, not the PoC numbers, decides whether Rust ever gets introduced.

## Conventions and known sharp edges

- Ruff runs with a large `select` set (pyflakes, pycodestyle, isort, pydocstyle/google, pyupgrade, bugbear, simplify, comprehensions, builtins, return, unused-args, type-checking, perflint, RUF) and a long `ignore` list that specifically permits Chinese characters (`RUF001-003`), missing docstrings (`D1xx`), long lines (`E501`), and bare `except` (`E722`). Per-file ignores drop `D` and `S101` for `tests/`, `test/`, `example/`. `line-length = 100`, double quotes.
- MyPy is a **hard gate** in both `quality.yml` and `release.yml` — the `continue-on-error` was removed by `establish-type-gate` (4.1/4.2), and the repo is at zero errors. `disallow_untyped_defs` is off globally but **on for `zoo_framework.utils.*`** via `[tool.mypy.overrides]`; the local pre-commit mypy hook runs at the **default** stage with `files: ^zoo_framework/` (so a doc-only commit skips it). Ruff and pytest are hard gates too.
- CI runs on Python 3.13 across ubuntu/windows/macos and requires `--cov-fail-under=30`. A `benchmark` job that ran `pytest tests/benchmarks/` (a directory that has never existed, with the step `continue-on-error`) was **removed** by `establish-type-gate` (6.4) — do not confuse that directory with the real `bench/` directory, which is unrelated (see below).
- The version lives in **three** places that must be bumped together: `pyproject.toml` (`[project].version`), `.env` (`VERSION`), and `zoo_framework/__init__.py` (`__version__`). They **had drifted**, and the reason is worth knowing: the release `sed` matched on the version **value**, so once `__init__.py` drifted the pattern matched nothing and the bump silently no-opped (it reported success while doing nothing). The sed now matches the **key** instead, so it is drift-proof. `[tool.bumpversion].current_version` is still stale. Note the *value* is deliberately not recorded here (it changes every release) — read the three files, or the `grep` in the release workflow, if you need it. The `release.yml` workflow bumps them on push to `dev` (patch, `-beta`) or `main` (minor, stable) and publishes to pypi.org.
- Release triggers only fire on changes under `zoo_framework/`, `pyproject.toml`, `.env`, or the workflow itself — doc-only and test-only commits on `dev`/`main` do not release.
- The legacy `setup.py` build path has been **removed**, together with `script/pro.{sh,bat}`. It could not have worked: `setup.py` imported `distutils`, which was dropped from the standard library in Python 3.12, i.e. before every version this project supports. Packaging is now entirely `pyproject.toml` + hatchling.
- `example/main.py` and `example/event/demo_event.py` were **corrected** against the current API by `establish-type-gate` (7.1/7.2): the former now calls `Master()` instead of `Master(1)`, the latter imports `event` from `zoo_framework.core` instead of `build.lib.zoo_framework`. Note `example/threads/demo_thread.py` is **not** a working demonstration of a scheduled worker: its `@worker(count=20)` registers through the **legacy** `worker_register`, while `Master` schedules from `WorkerRegistry` — so that worker is registered but never dispatched.
- The top-level `test/` directory contains only stale `__pycache__` artifacts, not sources; the live suite is `tests/`.
