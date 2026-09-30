# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Zoo Framework (`zoo-framework` on PyPI) is a multi-threaded Python framework built on a **zoo metaphor** that maps onto the concurrency primitives:

| Metaphor | Component | Role |
|---|---|---|
| 🦁 Animal | Worker | Task execution unit |
| 🏠 Cage | `@cage` / `ThreadSafeDict` | Thread-safe container, singleton scope |
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

- `@cage` (`core/aop/cage.py`) replaces the class with a factory function that returns a **cached singleton** keyed by class name in a module-global `ThreadSafeDict`. `EventReactorManager`, `EventChannelManager`, `EventChannelRegister`, `EventProvider`, `WaiterResultReactor`, and `EventWorker` are all caged. Callers write `EventReactorManager().dispatch(...)` — instantiating to reach a `@classmethod` on the singleton. State on those classes (`reactor_map`, `_channel_map`) is therefore shared across the whole process and leaks between tests.
- `@params` (`core/aop/params.py`) rewrites each `ParamsPath` class attribute into the resolved literal value, so the class ends up holding a plain value, not a handle. `ParamsPath(value, default, aliases)` resolves in the order **primary path → `aliases` → `default`**; `_resolve` tests `is not None`, so a configured falsy value (`False`/`0`/`""`) is honoured rather than treated as missing. `aliases` absorbs historical key names — `params/worker_params.py` uses it for `worker:pool:enable` vs the `worker:pool:enabled` that `zfc --create` used to emit, a mismatch that previously made the setting be **silently ignored**. **Resolution happens once, at first import of that params module, cached by `cls.__name__` alone** — the same name-keying pattern `@cage` uses, so two same-named params classes collide. `zoo_framework/params` is imported lazily (inside `Master._create_waiter`, `BaseWaiter.__init__`, `StateMachineWorker`) precisely so that `ParamsFactory` has read `config.json` first. Importing a params class before constructing `Master` (or calling `ParamsFactory(path)`) freezes the defaults instead — `ParamsFactory()` with a missing path returns early and silently leaves `config_params` empty.
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
- MyPy is `continue-on-error` in both `quality.yml` and `release.yml`; `disallow_untyped_defs` is off. Ruff and pytest are hard gates.
- CI runs on Python 3.13 across ubuntu/windows/macos and requires `--cov-fail-under=30`. `tests.yml` also references a `tests/benchmarks/` directory that does not exist (that step is `continue-on-error`) — do not confuse it with the real `bench/` directory, which is unrelated (see below).
- The version lives in **three** places that must be bumped together: `pyproject.toml` (`[project].version`), `.env` (`VERSION`), and `zoo_framework/__init__.py` (`__version__`). They are currently out of sync (0.5.3-beta vs 0.5.3-beta vs 0.1.1-beta), as is `[tool.bumpversion].current_version` (`0.1.1-beta`). The `release.yml` workflow bumps them by `sed` on push to `dev` (patch, `-beta`) or `main` (minor, stable) and publishes to pypi.org.
- Release triggers only fire on changes under `zoo_framework/`, `pyproject.toml`, `setup.py`, `.env`, or the workflow itself — doc-only and test-only commits on `dev`/`main` do not release.
- Both `pyproject.toml`/hatchling and a legacy `setup.py` (reading the version from `.env`) exist; `script/pro.{sh,bat}` still call `python setup.py sdist build` + `twine upload`.
- `example/main.py` calls `Master(1)` and `example/event/demo_event.py` imports from `build.lib.zoo_framework` — both are stale against the current API. `example/threads/demo_thread.py` is the example that reflects current usage.
- The top-level `test/` directory contains only stale `__pycache__` artifacts, not sources; the live suite is `tests/`.
