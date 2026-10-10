# 可上手的任务（Good First Issues）

这一页是**给第一次给本项目提 PR 的人**看的：每条都是自包含的小活，不需要读懂整个框架。
每一步的完整流程见
[`CONTRIBUTING.md`](https://github.com/YearsAlso/zoo-framework/blob/dev/CONTRIBUTING.md)
（其中"哪些改动不需要流程"一节说明文档 / 拼写 / 示例 / 注释类改动**不需要**先写 OpenSpec 提案）。

**认领方式**：在对应 issue 下评论一句你要做，避免两个人做同一件事。
issue tracker 是唯一真源，本页只是给人挑活的索引。

> **快照日期**：2026-10-10（`gh issue list` 全量核对）。标注"暂不可开始"的条目在阻塞项关闭后
> 会由维护者补上 `good first issue` 标签。

## 可以立即开始（2 条）

| 编号 | 任务 | 文件路径 | 量级 | 验收标准 | 使用者可见的结果 |
|---|---|---|---|---|---|
| [#131](https://github.com/YearsAlso/zoo-framework/issues/131) | `zfc --worker` 在项目外静默成功——留下游离 `workers/` 目录并返回 0 | `zoo_framework/cli/scaffold.py`、`zoo_framework/__main__.py`、`tests/test_scaffold_cli_contract.py` | 约 30 分钟 | 在没有 `config.json` 的普通目录执行 `zfc --worker my_task` 时：**非 0 退出码** + 一行能看懂的错误信息，且**不创建** `workers/`；已有项目内的正常用法不受影响；补一条用例守护"项目外必须失败" | 命令行不再"假装成功"——现在它会创建一个没人要的目录还报成功，用户以为做对了 |
| [#151](https://github.com/YearsAlso/zoo-framework/issues/151) | 修掉文档站上唯一的死链（`BRANCHING.md` → `../CONTRIBUTING.md`） | `docs/BRANCHING.md` | 约 15 分钟 | 该相对链接改为绝对 GitHub URL；非 strict `mkdocs build` 的**链接告警数从 1 变成 0** | 文档站"分支策略"一页上的链接可以点了——今天它是全站唯一的死链 |

## 暂不可开始（3 条，阻塞解除后开放）

| 编号 | 任务 | 文件路径 | 量级 | 验收标准 | 使用者可见的结果 |
|---|---|---|---|---|---|
| [#152](https://github.com/YearsAlso/zoo-framework/issues/152) | 脚手架 demo Worker 首轮输出告诉新人"下一步改哪个文件" | `zoo_framework/templates/__init__.py`、`tests/test_scaffold_templates.py` | 约 30 分钟 | `zfc --create demoapp && cd demoapp && timeout 8 python src/main.py` 的输出里，tick 行之后有一行指向**真实存在**的具体文件路径，且只出现一次（不刷屏）；全量 `pytest` 全绿 | 新人跑通 Quick Start 后，屏幕直接告诉他下一步编辑哪个文件，不用回文档里翻 |
| [#153](https://github.com/YearsAlso/zoo-framework/issues/153) | 新增 FastAPI 集成示例（把 Worker 嵌进 Web 服务） | `example/fastapi/app.py`（新增）、`example/README.md` | 约 30–60 分钟 | 示例按文件头注释的步骤能实际启动，`curl` 打端点能观察到 Worker 真的执行；`example/README.md` 表格新增一行（演示什么 / 怎么跑 / 期望输出）；**`pyproject.toml` 无改动**（示例依赖放注释里） | 读者能看到"把框架嵌进自己的 Web 服务"是什么样子——一个可复制可运行的文件，而不是需要自己补全的片段 |
| [#154](https://github.com/YearsAlso/zoo-framework/issues/154) | FAQ 补一组真实提问（中英各一问一答） | `README.md`、`README.zh.md`、`docs/FAQ.md` | 约 20 分钟 | 两份 README 的 FAQ 各增一组问答且位置对应；两半问句数相等、主题命中集合一致；`docs/FAQ.md` 有该主题详版条目 | 读者在 README 上直接看到这个问题的答案，不必翻源码或提 issue |

各条的阻塞来源（GitHub 上已建立 `blocked by` 关系）：

| 条目 | 阻塞来源 | 为什么 |
|---|---|---|
| #152 | [#110](https://github.com/YearsAlso/zoo-framework/issues/110) | 先要有"开箱即跑的 demo Worker"，才谈得上给它加提示 |
| #153 | [#116](https://github.com/YearsAlso/zoo-framework/issues/116) | `example/` 的残留清理与目录说明先行，避免两边同时改 `example/README.md` |
| #154 | [#122](https://github.com/YearsAlso/zoo-framework/issues/122) | README 的 FAQ 节由它引入 |

## 曾经考虑过、实测否掉的方向

留着这一段是为了省掉重复讨论——这两条在 [#123](https://github.com/YearsAlso/zoo-framework/issues/123)
里被当作候选提过，核实后都不成立：

- **"补 README 英文站缺失章节"** —— 实测两份 README 的三级标题 **15 : 15 逐一平行**
  （`grep -n "^### " README.md README.zh.md`），没有"缺失章节"；文档站按
  `mkdocs.yml` 的 `language: zh` 只发布中文，所以"英文站"也不存在，补它不是 30 分钟量级。
- **"给错误信息增加可搜索的关键词"** —— 用户可见的报错串已经是可检索的英文短语
  （如 `Must inherit from BaseWorker: …`）；代码里仅有的两处中文 `TypeError`
  （`zoo_framework/core/adaptive/stats_store.py`）被同函数的 `except` 就地捕获，
  **从不外泄给使用者**，所以没有可改的对外文案。

另：`zfc --worker` 生成类名未转 PascalCase（[#112](https://github.com/YearsAlso/zoo-framework/issues/112)）
看起来像典型的新手活，但实测**已经实现**（`_worker_names("My_Task")` 返回
`('My_Task_worker', 'MyTaskWorker')`），因此不适合作为上手任务。
