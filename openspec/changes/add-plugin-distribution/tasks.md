# tasks — add-plugin-distribution

## 0. 维护者裁定（实现前已定；如有异议，维护者可在实现前否决）

| 原 Open Question | 采用值 | 依据 |
|---|---|---|
| 要不要引入「技能」（`SKILL.md` 式渐进披露）这一概念 | **不引入**。只做「**扩展包**」这一个分发单位；技能是独立的一层语义，本变更不碰 | 维护者裁定；控制语义面，避免一次引入两层未成熟概念 |
| 与 import 期装饰器注册（`@worker` / `@event`）如何共存 | **信任只管「包加载」这一层，装饰器路径完全不动**。项目级信任决定的是「是否把包载入运行时」；直接 import 一个模块仍按现状在 import 期注册，**不给 import 加门禁** | 维护者裁定；import 加门禁会破坏既有注册路径与全部既有测试的语义 |
| 职责分层 | **发现与信任语义进内核**（它回答「谁被允许进入运行时」，属语义承诺）；**来源与安装器进插件层**，不加重零依赖默认负担 | 维护者裁定；见 design.md D2 |
| 三档与失败姿态 | 明确**内置 / 用户级 / 项目级**三档；**项目级默认需要显式信任**（flag 或配置）；**拒绝时明确报错，不静默跳过** | 维护者裁定；与「失败要大声」一致，见 design.md D4 |

## 1. 规格（spec-first）

- [x] 1.1 `specs/plugin-distribution/spec.md` 写入 ADDED Requirements（分发单位 / 三档信任 /
      同名取舍 / 逐类过滤 / 零包行为不变），Scenario 一律四级标题
- [x] 1.2 `openspec validate add-plugin-distribution --strict` 通过（输出：Change ... is valid）

## 2. 内核实现（`zoo_framework/core/extension.py`）

- [x] 2.1 `TrustTier` 枚举（内置 / 用户级 / 项目级）与档位优先级
- [x] 2.2 `ResourceFilter`（frozen，`from_patterns` 解析 `!` 前缀、`[]` 置空、`allows`、
      `merged_with` 增量合并），验证逐类过滤三种场景
- [x] 2.3 `ExtensionManifest`（`name` / `version` / `entry` / `resources` / `autoload`，
      `from_mapping`），非法清单抛 `ExtensionManifestError`
- [x] 2.4 `ExtensionPackage`（清单 + 档位 + 出处 + 是否受信）与 `ExtensionSource` 协议
- [x] 2.5 `resolve_conflicts()` 纯函数：替换 / 增量 / 无基底三条规则
- [x] 2.6 `ExtensionLoader`：`discover()` 汇总来源并定信任；`load()` **先校验全部信任再导入**
      （原子拒绝），未受信项目级包抛 `ExtensionTrustError`
- [x] 2.7 `ExtensionTrustError` 文本含包名、来源出处、显式信任方式

## 3. 插件层与配置

- [x] 3.1 `zoo_framework/plugin/sources.py`：`LocalPathSource`（按档位扫根目录子目录清单）
- [x] 3.2 `zoo_framework/plugin/sources.py`：`InstalledDistributionSource`
      （入口点组 `zoo_framework.extensions` + `importlib.resources`）
- [x] 3.3 `zoo_framework/params/extension_params.py`：`plugin:trustProject`（默认 `False`），
      **惰性导入**
- [x] 3.4 `zoo_framework/plugin/__init__.py`：再导出内核与来源，新增 `load_extensions()`
      便捷入口（显式参数优先，缺省读配置键）
- [x] 3.5 确认新增模块无模块级 / 类级可变容器（`test_process_state_registry` 通过）

## 4. 测试（`tests/test_extension_discovery.py`）

- [x] 4.1 本地路径来源发现 / 缺清单不发现 / 缺名称与坏 JSON 大声失败 / 根目录缺失跳过
- [x] 4.2 已安装发行物来源发现（monkeypatch 入口点 + 临时包路径）
- [x] 4.3 未受信项目级包被拒：**先证明该包被发现过**，再证明未导入任何包（含受信者），
      并断言错误文本含包名与信任方式（导入副作用写 marker，不用引用捕获断言）
- [x] 4.4 经参数 / 经配置键显式信任后加载成功
- [x] 4.5 用户级包无需显式信任
- [x] 4.6 同名取舍三规则（替换 / 增量 / 无基底）
- [x] 4.7 逐类过滤三场景（`[]` / `!glob` / 未声明）
- [x] 4.8 零来源时发现为空且不导入任何模块
- [x] 4.9 新增模块仅依赖标准库 / 框架自身（AST 顶层导入名静态扫描）+ 运行依赖集不新增

## 5. 文档同步

- [x] 5.1 `docs/ARCHITECTURE.md` §7 更新插件系统图与说明（含扩展包分发与信任）
- [x] 5.2 `docs/contributing/structure.md` 更新 `plugin/` 行，并**更正**
      `PluginManager.load_from_path` 的失实描述
- [x] 5.3 **不做**独立 `docs/guides/` 指南：分发语义已并入 `ARCHITECTURE.md` §7；
      独立用户向指南留作后续（避免为凑篇幅新造文档站页面）

## 6. 验收（门禁全部跑并留档）

- [x] 6.1 `pytest -q -p no:cacheprovider`：基线 1195 → 1220 passed（+23 新用例 +2
      `test_no_class_replacement` 对新模块的参数化）
- [x] 6.2 `ruff check zoo_framework` / `ruff check tests`：均 All checks passed
- [x] 6.3 `ruff format --check zoo_framework tests`：仍是既有 5 个测试文件待重排，无新增
- [x] 6.4 `mypy zoo_framework`：Success，110 source files（+3 新模块）
- [x] 6.5 断言注入验证（详见变更报告）：注入一 → 2 红；注入二 → 3 红；注入三 → 1 红；
      三次均按 md5 逐字节还原成功（`extension.py` = `2c6f5638…`）
