# 维护者待办

本页是**维护者自己**的工作队列：CI、合规、重构、治理。
它**不面向使用者**——使用者关心的能力方向见[路线图](roadmap.md)。

> 分开的理由：此前这些内部项与用户可见的路线图混在一起（同页既写「v1.0 里程碑」
> 又写「刷新 uv.lock」），访客读到的是「维护者在为一个不存在的受众做合规」，
> 而不是「这里有人在解决我的问题」。

---

## CI 与供应链

| 项 | 状态 | 备注 |
|---|---|---|
| 刷新 `uv.lock`、消除已知漏洞 | 未开始 | issue #93。当前 `uv lock --check` 失败 |
| 分支保护 + 要求 PR 审批 | 进行中 | issue #96（需仓库设置） |
| 申请 OpenSSF Best Practices 徽章 | 未开始 | issue #95；前置材料见 issue #120 |
| 收口 #89–#95 的实际生效状态 | 未开始 | issue #121 |

## 代码质量

| 项 | 状态 | 备注 |
|---|---|---|
| 补齐公开 API 签名缺失的类型注解 | 未开始 | issue #141。40 处 griffe 告警，`mkdocs build --strict` 因此不通过 |
| 修 `test_event_push_model` 的 macOS 间歇失败 | 未开始 | issue #144。会制造假红灯，对外部贡献者尤其劝退 |
| `bumpversion` 的 `current_version` 与 `project.version` 对齐 | 未开始 | issue #115（前者 0.8.0，后者 0.10.x） |

## 仓库卫生

| 项 | 状态 | 备注 |
|---|---|---|
| 清理 `example/redis.json`（与「无 broker」定位矛盾） | 未开始 | issue #116 |
| `example/agent` 子模块在普通 clone 下是空目录 | 未开始 | issue #116 |
| 文档里的测试数量与实际不符（367 / 662 vs 实测值） | 未开始 | issue #114 |

## 治理与规范

| 项 | 状态 | 备注 |
|---|---|---|
| 补齐 `GOVERNANCE` / `MAINTAINERS` / `ADOPTERS` / `security.txt` | 未开始 | issue #120 |
| 输出 `docs/SECURITY_MODEL.md` | 未开始 | issue #121 |
| 迁移到 PEP 639 许可证写法、补 `CITATION.cff` | 未开始 | issue #119 |
| 回填 `0.9.x` / `0.10.x` 的 CHANGELOG | 未开始 | issue #117（当前只有 2 条，而 PyPI 有 37 个版本） |
| 拆分 `CONTRIBUTING.md`（542 行）并开免流程通道 | 未开始 | issue #123 |

## 流程资产

| 项 | 状态 | 备注 |
|---|---|---|
| `openspec/changes/archive/**`（134 文件 / 7,776 行）降低曝光 | 未开始 | issue #123 |
| `.claude/`（52 文件 / 5,333 行）是否移出仓库根目录 | 未评估 | issue #123 |

---

*Last updated: 2026-10-10*
