# scaffold-demo-worker 任务清单

## 1. 模板与脚手架

- [x] 1.1 `worker_template` 增加示例用途的说明注释与 `_execute` 计数输出形态
      （`self._tick` 自增、单行含名字与计数）；确认 `--worker` 默认产出同形态而非
      重复渲染 demo 专属字样（验证：模板渲染结果 grep 无 "demo" 专属字样残留）
- [x] 1.2 `main_template` 静态预置 `SampleWorker` 导入行与注册条目；`SampleWorker`
      文件由 `create_func` 用 `worker_template` 渲染落进 `src/workers/`（验证：
      临时目录 `--create` 后导入 `src/main.py`，`WORKERS` 非空且条目与导入对应）
- [x] 1.3 幂等预案验证：在已 create 的项目再执行 `zfc --worker sample_worker`，
      入口不出现重复导入 / 重复注册行（验证：入口 grep 单次出现）
- [x] 1.4 `create_func` 末尾向 stdout 打印摘要：创建位置 / 生成文件量 / 下一步命令
      `cd <name> && python src/main.py`（验证：CliRunner invoke stdout 三要素齐备）

## 2. 测试

- [x] 2.1 `test_scaffold_templates.py`：`test_entry_imports` 的 `WORKERS == []`
      改断非空并含 SampleWorker 条目（docstring 标注"行为意图变更：#110"）
      （验证：新断言红/绿均可达）
- [x] 2.2 新增用例：开箱运行产生非 LogUtils 业务输出（临时目录跑入口、过滤日志、
      断言含 `[SampleWorker] tick #`）；计数两次取值单调递增（验证：临时目录实测）
- [x] 2.3 新增用例：`--create` 成功摘要三要素（位置/文件量/下一步命令）齐备；
      失败路径（目标已存在）不打印摘要（验证：两种路径各一用例）
- [x] 2.4 全量 `pytest` 全绿；既有断言除 2.1 外零改动（验证：`pytest` 通过，
      `git diff tests/` 只出现本轮意图内改动）

## 3. README 双语 Quick Start

- [x] 3.1 双语代码块标注 `zfc --worker` 为可选（demo Worker 已预置），删除原有
      "必须 `--worker` 才有 Worker"的暗示；注意 README 中 `->` 注释残留会被
      `test_inline_comments_are_stripped_from_examples` 拒绝（验证：该测试通过）
- [x] 3.2 代码块后贴期望业务输出行并注明与系统日志的区分；双语表述平行
      （验证：两半 `grep -in` 成对命中；`test_documented_examples_run_successfully` 通过）

## 4. 回归与验证

- [x] 4.1 全门禁本地预跑：`ruff check` / `ruff format`（README 内嵌代码块会被钩子
      归一，注意重新 add）/ `mypy` / `pytest --cov`（验证：全部通过）
- [x] 4.2 `openspec validate scaffold-demo-worker --strict` 通过（验证：退出码 0）
