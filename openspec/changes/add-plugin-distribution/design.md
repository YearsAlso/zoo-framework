# 设计：add-plugin-distribution

## Context

动机见 `proposal.md`。当前可动用的既有事实：

- 插件系统整个在 `zoo_framework/plugin/__init__.py` 一个模块里（`Plugin` / `PluginManager`
  / `WorkerDelayManager` / 延迟策略 + 模块级助手）。
- **`PluginManager.load_from_path` 在代码里从未存在**：`git log -S "load_from_path" --
  zoo_framework` 为空，全仓 `.py` grep 无命中；只有 `docs/ARCHITECTURE.md` 与
  `docs/contributing/structure.md` 把它当作既有方法写下。issue 正文据文档采信了它。
  本设计**不新增**该方法，而是把「信任门禁」落在新的加载器上，并**更正**这两处文档。
- 参数解析走 `ParamsPath` + `@params`，且 `zoo_framework.params` 必须**惰性导入**
  （`ParamsFactory` 先读 `config.json`），否则冻结在默认值。
- 既有参数类**无一使用可变默认值**（list/dict），因为 `@params` 会把解析结果写回
  **类属性**，而 `tests/test_process_state_registry.py` 会把类级可变容器判为未登记载体。
- 零依赖是本项目的核心卖点（`pyproject.toml` 无运行时依赖）。

## Goals / Non-Goals

**Goals:**

- 定义扩展包清单与四类资源（extensions / themes / prompts / examples）。
- 定义三档来源与信任门禁，项目级默认需显式信任，拒绝时大声报错。
- 定义同名多来源取舍与逐类资源过滤的可验证规则。
- 零包时行为不变；零新依赖。

**Non-Goals:**

- **不实现技能（SKILL.md 式渐进披露）**：按维护者裁定，本变更只有「扩展包」一个分发单位。
- **不实现下载式安装器**（`install` / `update` / `remove`）：PyPI 来源即「已安装发行物的发现」，
  安装交给既有包管理器（`pip install` / `git clone` 到来源根目录）。这也避免物理复制导致的
  重复 class / registry（`pi` 的 `peerDependencies` 约束针对的正是物理复制）。
- **不消费主题 / 提示模板 / 示例**：框架内暂无这些资源的消费方，本变更只把它们作为
  清单声明与过滤结果**如实暴露**，不虚构消费者。
- **不给 import 期装饰器注册（`@worker` / `@event`）加门禁**：按维护者裁定，信任只管
  「包加载」这一层；直接 import 一个模块仍按现状在 import 期注册。
- 不改 `PluginManager` 既有方法语义。

## Decisions

**D1 · 能力边界：新建 `plugin-distribution` capability**
`openspec/specs/` 下 `project-governance`（治理文件）与 `config-resolution`（参数解析
回退）均不描述插件或分发语义，全仓 specs 无一处提及插件。故新建 `plugin-distribution`。

**D2 · 分层：语义进内核、来源进插件层**
内核 `zoo_framework/core/extension.py` 只放**纯语义**：档位、清单、过滤器、冲突取舍、
信任门禁、来源协议（`Protocol`），不含任何 I/O。插件层
`zoo_framework/plugin/sources.py` 放**具体来源适配器**（本地路径 / 已安装发行物）。
内核不 import 任何具体来源；插件层 import 内核。既有 `plugin/__init__.py` 再导出并
提供便捷入口。备选（全放 `plugin/`）被否，因「谁被允许进入运行时」属语义承诺，且
将来内核的运行时自检需要它。

**D3 · 清单格式：`zoo-extension.json`**
字段 `name`（必需）/ `version` / `entry`（可导入的入口模块，触发注册；可为空表示纯数据包）/
`resources`（每类 glob 列表）/ `autoload`（默认 `true`）。JSON 便于零依赖解析，且与
`config.json` 同风格。备选（Python 模块清单）被否：执行任意代码来「读取声明」违背信任前置。

**D4 · 信任门禁原子化、失败大声**
`ExtensionLoader.load()` 先对**全部**解析结果校验信任，存在未受信任的项目级包时
**在导入任何包之前**抛 `ExtensionTrustError`（含包名、来源出处、显式信任方式）。
备选（逐个「跳过并告警」）被否：与「失败要大声」及维护者裁定相悖。

**D5 · 同名取舍：替换 + 增量 + 无基底**
见 spec 的三条规则。`autoload: false` 的增量语义按 `pi` 的「过滤增量」落为：包含项
合并、排除项合并、显式空过滤器置空该类。`resolve_conflicts()` 为纯函数，最易测。

**D6 · 过滤器语义**
`ResourceFilter`（frozen dataclass，字段为 `tuple`）：`includes` 默认 `("*",)`，
`excludes` 默认 `()`。`[]` → `includes=()`（该类全不加载）。`from_patterns()` 解析
`!` 前缀。`allows(name)` 先看 includes 再看 excludes。用 `fnmatch`（标准库）。

**D7 · 零依赖来源**
本地路径用 `pathlib` + `json`；已安装发行物用
`importlib.metadata.entry_points(group=...)` 定位入口点、`importlib.resources.files()`
读清单。二者皆标准库。入口点的 `value` 形如 `"<package>:<relative/manifest.json>"`；
入口模块须是可被 `importlib.resources.files()` 接受的可导入包（Python 3.11 下需为包）。

**D8 · 默认零副作用**
来源根默认**不配置**（空），`load_extensions()` 未配置来源即发现为空、加载为空操作；
框架启动路径（`Master`）**不调用**任何发现/加载入口，故未装扩展包时行为逐字节一致。

**D9 · 配置键只有一个、且惰性导入**
`zoo_framework/params/extension_params.py` 仅声明 `plugin:trustProject`（`bool`，
默认 `False`）——刻意**不**把路径列表放进参数类：`@params` 会把解析值写回类属性，
若为 list 会被 `test_process_state_registry` 判为未登记载体。来源根以显式参数传入。
该参数类只在 `load_extensions()` 内**惰性导入**，遵守既有冻结纪律。

**D10 · 信任参数的优先级**
`load_extensions(project_trusted=None)`：显式参数优先；为 `None` 时读
`ExtensionParams.TRUST_PROJECT`。用户级与内置级恒可信。

## Risks / Trade-offs

- [入口模块须为可导入包，限制单文件扩展包] → 文档写明；数据包可用空 `entry`。
- [`importlib.metadata.entry_points` 在 3.11 与 3.12 返回类型略有差异（`SelectableGroups`
  兼容层）] → 统一按 `group=` 关键字调用并迭代，二者一致。
- [参数类若在 `Master` 读配置前被导入会冻结默认值] → 惰性导入 + 文档注明；与既有参数类同纪律。
- [并未实现下载式安装，可能与期望不符] → 记入 Non-Goals，并在报告里显式提出。

## Migration Plan

纯新增加载路径，无数据迁移。既有 `Plugin` / `PluginManager` API 不变；未配置来源时不
产生任何运行时差异。回滚 = 删除新增文件与 `plugin/__init__.py` 的再导出。

## Open Questions

无（维护者已就四条关键分叉裁定，见 tasks.md §0）。
