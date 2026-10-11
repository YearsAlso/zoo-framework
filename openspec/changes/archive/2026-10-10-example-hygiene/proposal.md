# 提案：example-hygiene

## Why（为什么）

`example/` 是访客最可能翻看的地方，实测存在三处矛盾（2026-10-10，基线 0.10.6-beta）：

1. **redis 残留与「无 broker」核心定位直接冲突**：`example/redis.json`（port/host/db）+
   `example/config.json` 的 `"_exports": ["redis"]`。全仓库实测：`zoo_framework/` 内 redis
   零引用（grep 0 命中）、docs 中 redis 全部是"本框架**无**外部依赖"的对比陈述、
   `example/main.py` 与 `_exports` 加载链（`ParamsFactory`）不依赖任何 redis 文件内容。
   `_exports` 声明会把 `redis.json` 作为附加参数文件加载——但它承载的键不存在于任何
   `ParamsPath`，加载了也无处生效，纯属死配置。
2. **`example/agent` 子模块普通 clone 下为空目录，且零处文档说明**：全新 clone（不带
   `--recursive`）实测 `example/agent` 为空；README / README.zh / CONTRIBUTING / docs/
   全部零提及该子模块。访客看到空目录的解读只能是"项目坏了"。姊妹仓库 `zoo-code-agent`
   仍在活跃（main 分支存在）。
3. **`example/` 没有一个「复制即跑」的完整示例**：README 首屏的 30 秒示例是文档内片段；
   `example/` 下唯一的完整可运行示例是 `main.py`（state-machine 演示，实测可跑），但
   README 未指路；`demo_event.py` 只是注册了 reactor 的类（无场景联动），
   development.md 引用的 `example/basic_usage.py` **不存在**。

## What Changes（做什么）

### 逐条核对表（issue #116 5 条 → 处置）

| # | issue 表述 | 实测证据 | 定性 | 处置 |
|---|---|---|---|---|
| 1 | 删 redis 残留 | 上文证据 1：生产代码 / 测试引用两路全空；`_exports:["redis"]` 是死配置 | 成立 | **修**：删 `example/redis.json` + `config.json` 的 `"_exports": ["redis"]` |
| 2 | agent 子模块二选一 | 姊妹仓库活跃、它本身是消费者验证仓库（见 memory 记录：树内 submodule 已定，勿再议）；运营上属于另一条验证线 | 成立 | **修（选 b）**：保留 submodule；在 README Quick Start 「Contributing」节 clone 命令补 `--recursive` 提示 + 新增 `example/README.md` 说明"不带 `--recursive` 你会看到什么" |
| 3 | 新增最小完整示例 | README 已有 30 秒示例（`Hello from MyWorker! Count: N`），B 系列变更已实跑验证 | 部分成立（README 已有，example/ 未同步提供） | **修**：`example/minimal.py` = README 首屏示例落盘版（≤30 行，同输出）；两处正文互相指路 |
| 4 | 所有示例"照着跑通" | 实测：`main.py` 可跑（state 输出）；`threads/demo_thread.py` 无 `__main__` 块——独立运行静默退出（exit 0 无输出），但作为模块被 `main.py` 调度可跑；`demo_event.py` 可导入（reactor 注册），无独立场景 | 成立 | **修**：`demo_thread.py` 补 `__main__` 入口（独跑可见输出）；`demo_event.py` 补一个自包含的最小投递场景（否则只有 reactor 注册、没有运行场景）；development.md `basic_usage.py` 引用改为真实存在的 `minimal.py` |
| 5 | 补 `example/README.md` | 现状无任何说明文件 | 成立 | **修**：新增——每个文件演示什么、怎么跑、期望输出；子模块说明 |

### 验收锚点（对应 issue 验收标准）

- `grep -rn "redis" example/` → 0 命中
- 全新 clone：`example/README.md` 存在并说明 `git clone --recursive`（提交在主仓库，
  clone 即有；agent/(空) 的解读有据可查）
- `example/minimal.py` 实跑输出与 README 期望一致（PR 贴实际运行结果）
- 全量 pytest 全绿；doc-consistency 的文档免疫测试不因新增示例文件而红

## Capabilities（能力）

- **New**: `example-hygiene` — 示例目录与核心定位一致、每个示例可跑、入口有说明
- **Modified**: 无

## 影响（Impact）

- 删除：`example/redis.json`；`example/config.json` 的 `_exports` 键
- 修改：`example/threads/demo_thread.py`（补入口）、`example/event/demo_event.py`（补场景）、
  README.md / README.zh.md（clone 提示 + minimal 指路）
- 新增：`example/minimal.py`、`example/README.md`
- 不碰：`.gitmodules`（子模块决议选 b）、`docs/tutorial/05-scaffold.md`（讲的是 CLI 脚手架产物，不属于本 change）
