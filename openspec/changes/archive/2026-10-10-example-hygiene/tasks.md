# example-hygiene 任务清单

## 1. redis 残留清理（issue #116 第 1 条）

- [x] 1.1 删 `example/redis.json`；`example/config.json` 删 `"_exports": ["redis"]`
      （验证：`grep -rn "redis" example/` 零命中）
- [x] 1.2 删后实跑 `example/main.py` 确认配置加载不受影响（验证：启动日志正常）
## 2. 最小完整示例（issue #116 第 3 条）

- [x] 2.1 新增 `example/minimal.py`（README 首屏示例落盘版，≤30 行，同输出）
      （验证：实跑 `Hello from MyWorker! Count: 1/2/3`，与 README 一致；
      重定向管道下的块缓冲行为与 README 缓冲警示一致）
- [x] 2.2 README.md / README.zh.md 补指路（"落盘版在 example/minimal.py"）
      （验证：grep minimal.py 双语命中）

## 3. 现有示例可跑通（issue #116 第 4 条）

- [x] 3.1 `example/threads/demo_thread.py` 补 `__main__` 入口（独立运行可见输出；
      此前独跑 exit 0 无输出）（验证：实跑 `Test get i:[N]` 逐秒递增）
- [x] 3.2 `example/event/demo_event.py` 补自包含最小投递场景（`__main__` 块：
      EventProvider.push × 3 → EventWorker 消费 → reactor 打印；
      master.run() 阻塞故生产者走 daemon thread）
      （验证：实跑 pushes ×3 后 `on_change_test_number:…` ×3）
- [x] 3.3 development.md `python example/basic_usage.py`（L190）改为真实路径
      `python example/minimal.py`（验证：grep basic_usage 零命中）
- [x] 3.4 structure.md 的 example 过期宣称（`Master(1)` / `build.lib` —— 早已不成立）
      替换为指向 example/README.md 的现状描述（验证：grep "stale against/已过期" 零命中）

## 4. 子模块说明（issue #116 第 2 条，选 b）

- [x] 4.1 README.md/README.zh.md「Contributing」节 clone 命令改 `--recursive` 并附
      "不需要可省略"提示（验证：grep `--recursive` 双语命中）
- [x] 4.2 新增 `example/README.md`：minimal/main/threads/event/agent 全部条目的
      "演示什么 + 怎么跑 + 期望输出"，含 agent 空目录说明（`git submodule update
      --init example/agent`）（验证：人工核对 5 条目全覆盖；doc-consistency 测试全过）

## 5. 回归与验证

- [x] 5.1 门禁：ruff check 全过；全量 pytest **1029 passed**（验证：输出留痕）
- [x] 5.2 `openspec validate example-hygiene --strict` 通过（验证：0 警告）
- [x] 5.3 提交（`Closes #116`）+ md5 核对（验证：差异仅限预期文件）
  - 实测：提交 `f6d8858 docs(example): 示例可跑化 + redis 残留清理（#116）`，已推送
    `origin/perfect/docs`；提交正文含 `Closes #116` 与四段实跑输出（minimal.py /
    main.py / demo_thread.py / demo_event.py）；改动文件集 11 个，与本清单已勾条目
    逐项对应，未越范围
  - md5 核对：`example/main.py`、`example/event/__init__.py`、`example/threads/__init__.py`
    与 `/f/Python/zoo/.orca/tmp-bak/rh/example-hygiene/md5-before.txt` 逐字节一致；
    其余差异文件（`config.json`、`redis.json`(删)、`demo_event.py`、`demo_thread.py`）
    全部落在本清单已勾条目名下
- [x] 5.3b PR 正文贴实跑输出（验证：PR #171 正文「实跑输出（example-hygiene 的验收证据）」一节）
  - 实测：PR **#171**（`--base dev`）正文含三例的命令与输出——`minimal.py`
    （`Hello from MyWorker! Count: 1..3`）、`demo_thread.py`（`Test get i` 逐秒递增）、
    `demo_event.py`（`pushed` ×3 → `on_change_test_number` ×3）
  - 取证口径（如实记录）：本次贴入的是**重新实跑**的输出，不是回抄提交正文；并附带一条
    复现须知——`minimal.py` 的 `print` 走块缓冲，管道下需 `PYTHONUNBUFFERED=1`
    才能看到输出（同一命令默认缓冲时可见 `Hello` 行数为 0，与 README 的缓冲警示一致）
