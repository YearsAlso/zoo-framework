# 提案：add-plugin-distribution —— 扩展包的分发、发现与信任

## Why

框架有 `Plugin` 与 `PluginManager`，但**没有资源分发与信任模型**：第三方无法把
「一组扩展 + 提示模板 + 主题 + 示例」作为**一个单位**声明、分发与发现；也没有回答
「装进来之后，哪些是可信的」——现有插件机制只有注册面，没有任何关于**来源**与
**许可**的语义承诺（issue #247）。

对照 `pi`（`@earendil-works/pi-coding-agent` v1.0.4，MIT，`docs/packages.md`）已经把
这件事做完整：包来自多种来源，声明分 personal / project 两档，**项目档必须通过
project trust 才读取**。本变更把它的**分发单位**与**信任档位**语义借鉴过来，但按维护者
裁定**不实现技能（SKILL.md）那一层**。

## What Changes

- **新增「扩展包」这一唯一分发单位**：一个扩展包由清单描述（名称、版本、入口模块、
  按资源类型声明的过滤器、是否自动加载），可作为一个单位被发现与加载。
- **新增三档来源语义：内置 / 用户级 / 项目级**。用户级默认可信，**项目级默认需要显式
  信任**（调用参数或配置键 `plugin:trustProject`）；拒绝时**明确报错**，不静默跳过。
- **新增同名多来源的取舍规则**：高档位**替换**低档位（项目级 > 用户级 > 内置）；
  高档位条目声明 `autoload: false` 时**退化为过滤器增量**，不替换低档位条目。
- **新增逐类资源过滤**：每类资源可声明 glob 列表，`[]` 表示该类全不加载，
  `!glob` 表示排除。
- **分层落位**：发现与信任**语义**进内核（`zoo_framework/core/extension.py`）；
  具体来源适配器（本地路径 / 已安装发行物）进插件层（`zoo_framework/plugin/sources.py`）。
- **零新依赖**：来源适配只用标准库（`importlib.metadata` / `importlib.resources`）。
  **不装任何扩展包时，既有行为逐字节一致**。

## Capabilities

### New Capabilities

- `plugin-distribution`: 扩展包作为分发单位的发现、三档来源与信任门禁、同名冲突取舍、
  逐类资源过滤，以及零包时的行为不变承诺。

### Modified Capabilities

<!-- 无。既有 capability（project-governance / config-resolution 等）均不描述插件或分发语义，
     本变更新建独立 capability；理由见 design.md 的 D1。 -->

## Impact

- 新增：`zoo_framework/core/extension.py`（内核语义）、`zoo_framework/plugin/sources.py`
  （来源适配器）、`zoo_framework/params/extension_params.py`（`plugin:trustProject`）。
- 修改：`zoo_framework/plugin/__init__.py`（再导出内核与来源、新增 `load_extensions` 便捷入口）。
- 文档：`docs/ARCHITECTURE.md` §7、`docs/contributing/structure.md`（并**更正**两处对
  `PluginManager.load_from_path` 的失实描述——该方法在代码里**从未存在**，已用 grep 确认）。
- 测试：`tests/test_extension_discovery.py`。
- 依赖：**不新增任何第三方依赖**（`pyproject.toml` 的 `dependencies` 与 optional extra 均不改）。
