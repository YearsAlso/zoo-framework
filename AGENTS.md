# AGENTS.md — using Zoo Framework

This file is for any coding agent **writing code that *uses* Zoo Framework as a library**:
how to install it, how to declare a task unit, which mistakes are rejected and with which
error text, and how to check your own change.

It is not the repository's development guide. For **working *inside* this repository**
(branching, OpenSpec workflow, quality gates, module layout) read `CLAUDE.md` instead. The
two files do not overlap: nothing here is required to build the framework, and nothing there
is required to build an application with it.

## Install and version floor

```bash
pip install zoo-framework
```

**Python 3.11 or newer is required** (`requires-python = ">=3.11"`). Importing the package on
an older interpreter is not supported; check `python --version` before generating code. The
optional native-execution extension has its **own** floor (Python 3.13+) and is not published
yet, so its install is rejected with an explicit error on 3.11 — that does not affect the
pure-Python framework.

To scaffold an application instead of installing by hand:

```bash
zfc --create myapp     # project dir with src/, config.json, templates, and a demo Worker
zfc --worker my_task   # add my_task_worker.py to ./workers or ./src/workers
```

`Master()` reads `./config.json` relative to the working directory, and runs without one.

## A Worker must be registered as a **class**

This is the single most common mistake, and it is rejected loudly. `WorkerRegistry.register_class`
validates with `issubclass(worker_class, BaseWorker)` and therefore accepts **only a class**:

| What you passed | What you get |
|---|---|
| A function, or an instance | `TypeError: issubclass() arg 1 must be a class` |
| A class that is not a `BaseWorker` subclass | `TypeError: Must inherit from BaseWorker: <class 'your.module.YourWorker'>` |
| A subclass whose `__init__` needs arguments | `TypeError: <class 'your.module.YourWorker'> requires constructor arguments and cannot be lazily instantiated;use register_instance or register_factory instead` |

The third one is not arbitrary: a class registered this way is instantiated lazily, so the
framework refuses to register a class it cannot construct with no arguments. For those two
extra shapes use `register_instance` (a ready-made object; non-`BaseWorker` input raises
`TypeError: Must be BaseWorker instance: ...`) or `register_factory` (a zero-argument callable
returning a `BaseWorker`).

**The correct shape** — this one does not raise:

```python
from zoo_framework.core import Master
from zoo_framework.workers import BaseWorker


class OrderSync(BaseWorker):
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 5, "name": "OrderSync"})

    def _execute(self):
        sync_orders()


master = Master()
master.register_worker("OrderSync", OrderSync)  # a class, with a no-argument __init__
```

A Worker stays a class **independent of any decorator**: any wrapper that replaces the class
with a factory function fails the same way, because the registry checks the object it is given.

## Configuration is separate from implementation

A Worker depends on exactly one thing: the `props` dict handed to `super().__init__(...)`.
It has no visibility into framework internals, so writing one does not require reading the
framework's source or understanding how the scheduler, registry and event pipeline relate.

```python
super().__init__(
    {
        "is_loop": True,  # keep running across scheduling rounds; omit/false for single-shot
        "delay_time": 1.0,  # seconds to wait after each execution; a fixed interval, not a cron expression
        "name": "MyWorker",
    }
)
```

Read configuration from `config.json` (via the params layer), never from the Worker's own
environment scraping — and never edit framework internals to carry an application concern.

## Failures are explicit, never silently downgraded

Generated code cannot detect a silent downgrade; a loud error is the signal needed to
self-correct. These are the real, reproducible forms:

| Trigger | Behaviour |
|---|---|
| Requesting a dispatch mode that is not implemented (`process`) | `NotImplementedError: dispatch mode 'process' is not implemented; implemented modes are ['thread', 'thread_pool']` |
| An unrecognised `worker:runPolicy` value in config | `ValueError: unknown run policy 'nope'; expected one of ['simple', 'stable', 'safe']` |
| An unrecognised pool backpressure policy | `ValueError: unknown backpressure policy 'nope'; expected one of ['expand', 'queue', 'reject']` |
| Registering a Worker as a function or an instance | `TypeError: issubclass() arg 1 must be a class` |
| A text file in an unexpected encoding | a warning naming the file: `file <path> is not UTF-8; it was read with the platform default encoding <encoding>;consider migrating the file to UTF-8` |

An unknown configuration value is **never** silently replaced by a default, and an
unimplemented mode is **never** silently executed as another mode. If generated code appears
to work while the configuration says something the framework does not implement, the
configuration is being ignored — do not paper over it.

## What this library does not do

Do not generate code that assumes these exist; each is a deliberate scope decision, not an
unfinished feature:

- **Multi-process execution** — not implemented. The mode constants are placeholders and a
  request for them is rejected (see the `NotImplementedError` above).
- **Cron expressions** — not supported. Only a fixed `delay_time` interval exists; for cron
  use APScheduler.
- **Cross-machine work** — not supported. Use Celery when a task must leave the process.
- **Health monitoring metrics** — the metric pipeline is not yet wired, so
  `get_health_report()` always reports `execute_count: 0`. Do not use it as an alerting or
  readiness source.

Also: a Worker that exceeds its timeout is **not** force-killed. The framework records the
timeout, marks the Worker unhealthy, logs it, and stops dispatching it — a still-running
`_execute()` keeps running (CPython cannot safely interrupt a thread). Do not write code that
depends on a running `_execute()` being interrupted.

## Verify your change

Run the suite from the repository root:

```bash
pytest                                        # whole suite
pytest tests/test_worker.py::TestBaseWorker::test_worker_execute   # a single test
```

The suite covers the core contracts (worker lifecycle, scheduling, the event pipeline, state
persistence), so a change can be judged by running it rather than by asking a human to read
it. Two more checks are useful when generated code touches configuration or the public
surface:

```bash
ruff check zoo_framework
mypy zoo_framework
```

## Where to look next

- `llms.txt` (repository root) — a compact index of the framework, its scope and its links.
- `docs/FAQ.md` — natural-language questions this project is commonly asked.
- `docs/api/README.md` — API reference generated from docstrings.
- `example/minimal.py` — a complete, runnable Worker.
