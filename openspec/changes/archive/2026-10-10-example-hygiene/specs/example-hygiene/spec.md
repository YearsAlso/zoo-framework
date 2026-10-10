# example-hygiene Spec Delta — example-hygiene

## ADDED Requirements

### Requirement: 示例目录 MUST 与核心定位一致，死配置 MUST NOT 留驻

`example/` SHALL 只包含与框架核心定位（无外部依赖、无 broker）一致的示例；示例配置
中不得出现指向未接线集成的键/文件（如 redis）——若确需展示可选集成，MUST 带明确的
「可选集成示例，未实现」标注而不是无标注的活跃配置。

#### Scenario: redis 残留清除
- **WHEN** `grep -rn "redis" example/`
- **THEN** 零命中（redis.json 删除，config.json 的 `_exports` 声明删除）

#### Scenario: 示例配置只含活跃键
- **WHEN** 检查 `example/config.json` 的每个键
- **THEN** 都能被 `ParamsPath` 实际解析（`log` / `stateMachine` / `worker` 等活跃键），
  无指向不存在参数的 `_exports` 引用

### Requirement: 每个示例 MUST 可独立运行或文件顶注明不可单独运行

`example/` 下每个 `.py` 文件 SHALL 满足之一：带 `__main__` 入口可独立运行并产生
清晰输出；或作为模块被其他示例组合使用（此时其职责由组合方文件与 `example/README.md`
说明）。文档中引用的示例路径 SHALL 真实存在。

#### Scenario: 引用路径真实
- **WHEN** 读取 `docs/contributing/development.md` 的示例运行命令
- **THEN** 命令里的每个路径都存在于仓库（如 `example/minimal.py` 取代不存在的
  `basic_usage.py`）

#### Scenario: 独立示例有输出
- **WHEN** 在本机实跑 `example/minimal.py`、`example/main.py`、
  `example/event/demo_event.py`（限时 + Ctrl-C 语义）
- **THEN** 每个在数秒内产生与 `example/README.md` 描述一致的清晰输出
  （实跑结果记录于 tasks.md）

### Requirement: 子模块空目录 MUST 有文档说明，clone 指引 MUST 读得懂

`example/agent` SHALL 保留为 git submodule（指向姊妹仓库 `zoo-code-agent`，树内
submodule 决议不变）；主 README 的 clone 指引 SHALL 提及 `--recursive`（或单独的
`git submodule update --init` 路径）；`example/README.md` SHALL 存在并逐一说明
每个条目演示什么、怎么跑、期望输出，以及"没有 `--recursive` 时 `example/agent`
是空目录、该怎么补"。

#### Scenario: example/README 存在且覆盖全部条目
- **WHEN** 读取 `example/README.md`
- **THEN** 覆盖 `minimal.py` / `main.py` / `threads/` / `event/` / `agent/` 全部条目，
  每个含"演示什么 + 怎么跑 + 期望输出"，并含子模块空目录说明

#### Scenario: clone 指引提及子模块获取方式
- **WHEN** 读取主 README（en/zh）与 CONTRIBUTING.md 的 clone 命令附近说明
- **THEN** 有一句说明 `--recursive`（或 `git submodule update --init`）获取
  `example/agent`
