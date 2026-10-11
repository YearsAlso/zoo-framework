# quiet-default-logs 任务清单

## 1. 日志降噪

- [x] 1.1 `base_worker.run()` 两处 `LogUtils.info`（Start/Stop）→ `LogUtils.debug`
      （验证：默认级别下 caplog 断言无该记录；debug 配置下重新可见）
- [x] 1.2 `master.py` SVM 三处（registered / monitoring started / setup completed）
      改写为如实措辞（metrics input not wired; get_health_report() returns zeros）
      并降为 debug；unregistered / monitoring stopped 仅改如实措辞保持级别
      （验证：grep `SVM monitoring started` 零命中；`[Aa]ssert.*monitor` 相关
      断言存在）
- [x] 1.3 `state_machine_work.py` / `persistence_scheduler.py` / 反应器注册日志
      **不改**（实查清单已裁定非"断言不实"）（验证：`git diff` 无这些文件）

## 2. 脚手架配置

- [x] 2.1 `DEFAULT_CONF` 的 `log.level` `debug` → `warning`（验证：
      `--create` 产出 config.json 中级别为 warning 的用例通过）
- [x] 2.2 验收实测：临时目录 `zfc --create demoapp && timeout 10 python src/main.py`
      stdout（业务输出不计入）+ 默认级别 stderr ≤ 5 行（验证：实测记录行数）

## 3. 测试

- [x] 3.1 新增用例：默认 root level 下 Start/Stop 无可输出记录；`log.level=debug`
      时重新可见（验证：两个方向各一 assertion）
- [x] 3.2 新增用例：SVM 日志文案不含 `SVM monitoring started` 等断言性措辞，
      含"not wired / zeros"如实表述（验证：文案正反各一）
- [x] 3.3 全量 `pytest` 全绿；`ruff check` / `ruff format` / `mypy` 过
      （验证：门禁全通过）

## 4. 文档核对与验证

- [x] 4.1 README 双语 Quick Start "期望输出"描述按降噪后观感核对（tick 仍是唯一
      可见业务输出；如原有"系统日志长得不一样"措辞仍成立则零改动）（验证：措辞核查）
- [x] 4.2 `openspec validate quiet-default-logs --strict` 通过（验证：退出码 0）
