# example-hygiene 任务清单

## 1. redis 残留清理（issue #116 第 1 条）

- [ ] 1.1 删 `example/redis.json`；`example/config.json` 删 `"_exports": ["redis"]`
      （验证：`grep -rn "redis" example/` 零命中）
- [ ] 1.2 删后实跑 `example/main.py` 确认配置加载不受影响（验证：启动日志正常）

## 2. 最小完整示例（issue #116 第 3 条）

- [ ] 2.1 新增 `example/minimal.py`（README 首屏示例落盘版，≤30 行，同输出）
      （验证：实跑输出 `Hello from MyWorker! Count: N` 与 README 一致）
- [ ] 2.2 README.md / README.zh.md 补指路（"落盘版在 example/minimal.py"）
      （验证：grep minimal.py 命中）

## 3. 现有示例可跑通（issue #116 第 4 条）

- [ ] 3.1 `example/threads/demo_thread.py` 补 `__main__` 入口（独立运行可见输出）
      （验证：实跑数秒内出现 Test get i 输出）
- [ ] 3.2 `example/event/demo_event.py` 补自包含最小投递场景（`__main__` 块）
      （验证：实跑数秒内 reactor 收到事件并打印）
- [ ] 3.3 development.md `python example/basic_usage.py`（L190）改为真实路径
      `python example/minimal.py`（验证：grep basic_usage 零命中）

## 4. 子模块说明（issue #116 第 2 条，选 b）

- [ ] 4.1 README.md/README.zh.md「Contributing」节 clone 命令旁补 `--recursive` 提示
      （验证：grep `--recursive` 命中两处）
- [ ] 4.2 新增 `example/README.md`：每个条目（minimal/demo_thread/demo_event/main/
      agent）的"演示什么 + 怎么跑 + 期望输出"，含 agent 空目录说明（验证：人工核对）

## 5. 回归与验证

- [ ] 5.1 门禁：ruff check / ruff format（改动文件范围）；全量 pytest 全绿
      （验证：输出留痕）
- [ ] 5.2 `openspec validate example-hygiene --strict`（验证：0 警告）
- [ ] 5.3 提交（`Closes #116`）+ md5 核对 + PR 正文贴实跑输出
      （验证：与 /f/Python/zoo/.orca/tmp-bak/rh/example-hygiene/md5-before.txt 差异仅限预期文件）
