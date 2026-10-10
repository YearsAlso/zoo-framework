# agent-discoverability 设计

动机与范围见 `proposal.md`。本文只记"怎么做"与为什么这样做。

## Context

三处必须先摆出来的现状（都是实测，不是推断）：

**1. 内容大多已经存在，缺的是入口。**

| 已有 | 缺口 |
|---|---|
| `docs/FAQ.md`：10 组自然语言问句，覆盖 issue 点名的全部问题，中文 | README 没链接它，英文检索语料里没有它 |
| README `### Built for AI-agent-generated code`：三步示例 + 「失败要大声」四行表 | README 里没有**问句形态**的答案 |
| `CLAUDE.md`：仓库内部开发指引（SDD、门禁、架构） | 没有面向"用本库写代码"的公开说明 |
| `example/minimal.py`：可运行的最小示例 | 没有被任何检索入口索引 |

**2. issue 引用的两份草稿不存在。** issue 写"现成内容见 `artifacts/llms.txt` / `artifacts/AGENTS.md`"，
但本机搜 `F:\Python\zoo`、`.orca/`、`F:\` 三层均无 `artifacts/` 目录与这两个文件。两份文件按
issue 的内容清单从仓库实测状态写出。

**3. 站点可达性的实测结果决定 URL 怎么选（2026-10-10，逐个 curl）：**

| URL | 状态 | 说明 |
|---|---|---|
| `https://yearsalso.github.io/zoo-framework/` | 200 | 本站文档站根（`mkdocs.yml` 的 `site_url`） |
| `.../zoo-framework/benchmark/` | 200 | 该站上存在的页面 |
| `.../zoo-framework/api/`、`/install/`、`/FAQ/` | **404** | `docs.yml` 只由 `main` 触发，`main` 落后 88 个提交 |
| `https://yearsalso.github.io/zoo-bench/` | 200 | 独立 benchmark 报告站 |
| `https://yearsalso.github.io/zoo-framework-doc/` 根 | 200 | 但 `/FAQ/`、`/api/`、`/tutorial/` 全 404（空壳） |
| `https://pypi.org/project/zoo-framework/` | 200 | |
| `.../github.com/.../blob/dev/docs/FAQ.md`、`blob/dev/docs/api/README.md`、`blob/dev/CHANGELOG.md`、`blob/dev/README.md` | 200 | dev 分支上的四个文件 |

`raw.githubusercontent.com` 在本机全部连接失败（curl 退出码 35/000），因此**不采用 raw 链接**。

## Goals / Non-Goals

**Goals**

- 检索入口齐备且**内容准确**：`llms.txt`、`AGENTS.md`、README FAQ 三处对"支持 / 不支持"的
  表述与特性表逐项一致。
- 把"三处一致性"变成 CI 断言，而不是靠人记得同步（本仓库对重复内容的既有处理方式）。
- 站点根的 `/llms.txt` 在合并到 `main` 后可达——复用既有构建钩子，不产生第二份手写副本。

**Non-Goals**

- 不写 `llms-full.txt` 或任何 llms.txt 的可选变体（约定里是可选，本变更不做）。
- 不做 FAQ 的结构化数据（JSON-LD / schema.org）。
- 不改 `docs/FAQ.md` 正文、不改 README 的特性表与对比表、不改 `CLAUDE.md`、不改
  `zoo_framework/**`、不新增第三方依赖。
- 不修 `docs/FAQ.md` 里已过期的 `uv.lock` 一句（与 issue #122 无关，另行报告给维护者）。

## Decisions

### D1 README FAQ 是"短答索引"，`docs/FAQ.md` 是详版真源，一致性交给断言

- **选择**：README 每组 1–3 行短答；每题答案末给出 `docs/FAQ.md` 的绝对链接；两处一致性由
  `tests/` 的机械断言守。
- **备选**：①README 放完整 FAQ（两处同一批问答、无机制守，正是 `requirements*.txt` 漂移的老路）；
  ②README 只放链接不写答案（不满足 issue 验收：README 需 ≥8 组 FAQ，LLM 读 README 拿不到答案）。
- **理由**：本仓库对重复内容的既有处理方式就是"真源唯一 + 用测试防漂移"（`#120` 的
  `.well-known` 副本禁止、`#121` 的依赖清单唯一性），沿用同一条架构取向，而不是新开一种做法。

### D2 断言比"主题覆盖"与"支持/不支持结论"，不比逐字文本

- **选择**：测试里维护一张**主题 → 关键词集合**的映射表（10 个 issue 点名主题）；断言
  ①两份 README 的 FAQ 每组问句都命中某个主题；②每个主题至少命中一次；③`docs/FAQ.md` 也
  至少命中一次。另外单独断言多进程 / cron / 健康指标三项的**否定口径**与特性表一致。
- **备选**：逐字比对中英两份 FAQ（翻译必然不同，断言会变成维护负担）；只数问句数量
  （删掉一个主题、再补一个无关问题就能骗过）。
- **理由**：短答是详版的压缩，逐字比对必然失败且无意义；而"主题集合 + 否定口径"恰好是
  这次真正要守的两件事，且注入违规时**会红**。
- **补注**：issue 的"支持多进程 / 跨机器吗？"在 README 里是一问（覆盖面更全），它在详版里
  对应 `docs/FAQ.md` 的「支持多进程吗」与 Celery 一节的"需要跨机器就用 Celery"两处——主题
  映射表按主题而不是按标题一一对应，正是为此。

### D3 绝对 URL 只写**今天实测可达**的那些

- **选择**：`llms.txt` 里写四项——文档站根（200）、benchmark 报告（200）、API 参考（dev blob，200）、
  CHANGELOG（dev blob，200）；站点**子页不写**（今天 404）。
- **备选**：①全写站点页面 URL（今天是死链，违背"内容必须准确"）；②全写 GitHub/PyPI
  （丢掉文档站的入口，而文档站才是本项目的用户文档）。
- **理由**：`docs.yml` 只由 `main` 触发，而本变更在 `perfect/docs` 上——站点子页在合并前
  不可能存在。用 dev blob URL 代替，是"今天可核对"与"合并后仍然有效"两者的交集。
- **配套断言**：`llms.txt` 里的站点 URL 必须落在**白名单**内（白名单即上表实测可达的 URL
  前缀）。有人凭直觉写 `.../zoo-framework/api/` 这种今天 404 的链接会立刻变红。

### D4 站点根发布复用既有构建钩子，复制清单显式化

- **选择**：把 `scripts/mkdocs_hooks.py` 里"复制哪些仓库根文件进站点产物"改成一份显式清单
  （`.well-known/` 目录 + `llms.txt` 文件），逐项"缺失即构建失败"。
- **备选**：①`docs/` 下放副本（第二份手写真源；且它会被 mkdocs 当页面渲染）；②新写一个
  workflow 复制（第二套发布路径，与 `#120` 已确立的机制重复）。
- **理由**：`#120` 已经为 `.well-known/security.txt` 建立并验证了"真源唯一 + 构建期复制 +
  源缺失即失败"这套机制；`llms.txt` 是同一形态的第二个使用者，复用它的边际成本最小、
  架构一致性最高。
- **实现约束**：`.well-known/` 的现有语义（目录缺失即失败）MUST 保持不变——它是已归档规格
  里的一条要求。

### D5 `docs.yml` 触发路径补 `llms.txt`

- **理由**：该文件的注释已为 `.well-known/**` 写明同一理由（只改内容却不触发部署，已发布
  站点会一直带着旧版本）。`llms.txt` 现在是站点产物，同理会踩同一个坑。
- **注意**：触发路径里已有 `README.md`，因此 README 的 FAQ 改动会正常触发部署；`llms.txt`
  是唯一新增项。

### D6 机械校验离线，联网结论写成可复跑命令

- **选择**：新增 `tests/test_agent_discoverability.py`（pytest、无网络）；绝对 URL 的可达性
  实测表写进本设计的 D3，并在文件头注明复核方式（curl 一遍）。
- **理由**：沿用 `#121` 的 D6——三平台 CI 上做联网断言只会带来假红；而"URL 白名单"这一离线
  断言已经能拦住最常见的错误（写站点子页链接）。

### D7 三份新内容的语言

- `llms.txt` / `AGENTS.md`：英文。面向的是通用编码 agent 与英文检索语料（issue 的定位
  "为 AI 生成的代码而设计"针对的正是这批读者）。
- README FAQ：`README.md` 英文、`README.zh.md` 中文——各自本地化，不互译粘贴。

## Risks / Trade-offs

- **[新写的 llms.txt/AGENTS.md 里出现未实现能力 → 制造新的自相矛盾]**
  → 断言从 **README 特性表**取真源（解析 ❌/⚠️ 行），再检查对应关键词在 `llms.txt` 里
  处于否定语境；特性表变了断言跟着变，不需要在测试里再抄一份能力清单。
- **[README FAQ 与 `docs/FAQ.md` 产生第二口径]**
  → D2 的主题覆盖断言 + 否定口径断言；每题短答末附详版链接，读者要细节有去处。
- **[中英两份 FAQ 漂移]** → 断言比对两份的**问句数与主题命中集合**（不比对译文）。
- **[FAQ 稀释 README 首屏]** → FAQ 放 README 尾部（Contributing 之后、License 之前），
  首屏区块（"30 秒"、对比表、AI-agent 一节）一律不动——那是 `readme-first-screen` 已定稿的资产。
- **[AGENTS.md 的报错文本与代码漂移]**
  → 断言直接**从 `zoo_framework` 源码里抓真实 raise 文本**（`issubclass()` 形态、
  `requires constructor arguments` 形态、`unknown run policy` 形态、`is not implemented`
  形态）与 `AGENTS.md`/README 里引用的文本比对；代码改文案而文档没跟上会红。
- **[站点根 `/llms.txt` 在合并前不可达]**
  → 按 `#121` 的同一口径如实标注"合并到默认分支后才生效"，**不声称已生效**；本变更只保证
  构建钩子与触发路径就位。
