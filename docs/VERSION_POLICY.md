# 版本政策

本页说明：哪些东西属于**公开 API**、破坏性变更如何通知、弃用提前多久公告、
以及支持的 Python 版本范围。

它与 [`SECURITY.md`](https://github.com/YearsAlso/zoo-framework/blob/dev/SECURITY.md) 的支持版本表**保持同一口径**——若两者出现分歧，
以本页为准并同步修正 `SECURITY.md`。

---

## 版本号

遵循[语义化版本](https://semver.org/lang/zh-CN/)：`MAJOR.MINOR.PATCH`。

当前处于 **`0.x` 阶段**（最新为 `0.10.x`），因此：

| 变更类型 | 允许出现在 | 说明 |
|---|---|---|
| 新增能力 | MINOR | 向后兼容 |
| Bug 修复 | PATCH | 向后兼容 |
| **破坏性变更** | **MINOR** | `0.x` 阶段 MINOR 允许破坏，**但 MUST 在 `CHANGELOG.md` 标注 `BREAKING` 并给出迁移方式** |
| 破坏性变更 | PATCH | ❌ 不出现 |

> **`0.x` 不代表可以随意破坏。** 承诺是：**每一次破坏都要被明确记下来、并给出迁移路径**。
> 迁移方式见[迁移指南](MIGRATION.md)。

---

## 哪些属于公开 API

| 属于公开 API | 说明 |
|---|---|
| `zoo_framework` 各包 `__all__` 中导出的名字 | 权威清单见 [API 参考](api/README.md)（从代码自动生成） |
| 文档化的配置键 | 如 `worker:mode`、`worker:runPolicy`、`event:delay`、`stateMachine:delay` |
| 状态文件的落盘格式 | `zooStates.pic` 与 `backups/` 的结构 |
| `zfc` 命令行表面 | 参数、退出码、产物路径 |
| 本页与 [迁移指南](MIGRATION.md) 中明文承诺的行为 | — |

| 不属于公开 API | 说明 |
|---|---|
| 下划线开头的名字 | 私有，随时可变 |
| 未出现在 `__all__` 中的模块内符号 | 内部实现 |
| 模块的文件路径 | 除 `zoo_framework.*` 的包路径外，内部模块位置可变 |
| 日志文本与 emoji | 会变，不要解析它 |

**判定方法**：若某个名字在 [API 参考](api/README.md) 中出现，它属于公开 API。
若不在，它随时可能变。

---

## 弃用与删除

```mermaid
flowchart LR
    A["标记 deprecated<br/>（发 DeprecationWarning）"] --> B["至少保留 1 个 MINOR"]
    B --> C["在 CHANGELOG 标注 BREAKING"]
    C --> D["删除"]
```

承诺：

1. **弃用 MUST 产生 `DeprecationWarning`**，且告警文本 MUST 说明替代写法。
   （正面例子：`@worker` 的告警文本明确写了"I does not hook into dispatch... use `Master.register_worker` instead"）
2. **弃用后至少保留一个 MINOR 版本**再删除。
3. **删除 MUST 在 `CHANGELOG.md` 的 `BREAKING` 段出现**，并同步更新[迁移指南](MIGRATION.md)。
4. 报错信息 SHOULD 可被搜索、可自我纠正——错误应说明**缺什么**与**下一步怎么做**，
   而不是只给一个类型错误。这对 AI agent 生成的代码尤为重要。

---

## Python 版本支持

| 项 | 值 |
|---|---|
| 当前下界 | **3.13**（见 `pyproject.toml` 的 `requires-python`） |
| CI 覆盖 | 见仓库 `.github/workflows/tests.yml` 的矩阵 |

**支持策略**：下界一旦确定，**降低它是兼容的**（更多人能装），**提高它才需要公告**。

> 下界当前是 `3.13`，且**已知偏高**——它会把大量仍在 3.10–3.12 的环境排除在外。
> 这是一项在跟踪中的待决事项（issue #124），结论出来后会同步到本页。

---

## 发布节奏

**没有固定节奏。** 版本随实际变更发布，不做时间承诺。

---

## 与安全支持的关系

| 版本线 | 安全修复 |
|---|---|
| PyPI 上的最新发布 | ✅ |
| 最新 minor 线 | ✅ 仅近期修复 |
| 更早的 minor 线 | ❌ 请升级 |
| `1.0` 及以后（未来） | ✅ |

完整说明与漏洞报送渠道见 [`SECURITY.md`](https://github.com/YearsAlso/zoo-framework/blob/dev/SECURITY.md)。
