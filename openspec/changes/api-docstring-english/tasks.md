# Tasks: api-docstring-english

## 1. 报错/日志消息英文化（9 文件，22 处）

- [ ] 1.1 `core/container/container.py`：7 处 raise 消息换英文（作用域/注册/替换语义不变）
- [ ] 1.2 `core/container/registration.py`：1 处
- [ ] 1.3 `core/container/scope.py`：5 处（含「MUST NOT 静默退回进程级」语义级消息，译 MUST NOT）
- [ ] 1.4 `core/process_state.py`：1 处
- [ ] 1.5 `core/waiter/base_waiter.py`：N 处（grep 清单为准）
- [ ] 1.6 `core/waiter/scheduler_model.py`：N 处
- [ ] 1.7 `fifo/node/event_fifo_node.py`：N 处
- [ ] 1.8 `reactor/event_reactor.py`：N 处
- [ ] 1.9 `workers/async_worker.py`：N 处

## 2. `__init__` 导出面英文化

- [ ] 2.1 顶层 `zoo_framework/__init__.py`：docstring 换英文 + 版本行「版本: 0.8.0」过期信息移除
- [ ] 2.2 各子包 `__init__.py` 中文 docstring（grep 清单为准，core/workers/event/fifo/reactor/params/utils 共 2–3 处）

## 3. 公开类 docstring 英文化（grep 清单为准，逐文件）

- [ ] 3.1 `core/master.py`、`core/params_factory.py`、`core/params_path.py`、`core/persistence_scheduler.py`、`core/worker_registry.py`、`core/zoo_thread.py`、`core/run_identity.py`、`core/process_state.py`
- [ ] 3.2 `core/waiter/*`、`core/container/*`、`core/aop/*`
- [ ] 3.3 `workers/*`（base/event/async/props/result/register）
- [ ] 3.4 `statemachine/*`、`event/*`、`fifo/*`、`reactor/*`、`params/*`、`utils/*`

## 4. 验证（design D4）

- [ ] 4.1 `grep -rPn '(raise|logger|print).*[\x{4e00}-\x{9fff}]' zoo_framework --include='*.py'` 零命中
- [ ] 4.2 `help('zoo_framework')` 输出无中文、GBK 控制台无乱码
- [ ] 4.3 `pytest` 全绿
- [ ] 4.4 `mypy zoo_framework` 零错误
- [ ] 4.5 `ruff check zoo_framework` 零错误
