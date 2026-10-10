# agent-discoverability 任务清单

## 1. `llms.txt`（issue 第 2 条）

- [x] 1.1 新增仓库根 `llms.txt`：H1 标题 + 引用式摘要（`> `）+ 分节链接列表，六类内容齐备：
      这是什么 / 什么时候用 / 什么时候**不要**用 / 核心概念 / 最小可运行示例 / 外部绝对 URL
      （验证：文件内能定位到这六类；首行是 H1、摘要是引用块）
- [x] 1.2 「不要用」清单明写三条替代：跨机器 → Celery、cron → APScheduler、多进程 → 本框架
      未实现；核心概念用**功能名**并显式声明"隐喻只影响命名、不影响语义"
      （验证：三条替代各自可定位；隐喻声明存在）
- [x] 1.3 最小可运行示例与 `example/minimal.py` 的事实一致（同样的类名、`is_loop` /
      `delay_time` 语义、注册的是**类**）；绝对 URL 只写**今天实测 200** 的四项——文档站根、
      benchmark 报告、API 参考（dev blob）、CHANGELOG（dev blob）
      （验证：每个 URL 逐个 curl 实测 200；文件内不出现站点子页链接）

## 2. `AGENTS.md`（issue 第 2 条）

- [x] 2.1 新增仓库根 `AGENTS.md`：安装方式与版本门槛（`pip install zoo-framework`、Python 3.13+）、
      配置与实现分离（Worker 只依赖 `props`）、「失败要大声」至少三例并附**实测报错串**、
      验证改动要跑的测试命令
      （验证：四类内容齐备；报错串与 `zoo_framework` 源码实际 raise 的文本逐字一致）
- [x] 2.2 Worker MUST 以**类**注册：写明被拒绝的输入类型与各自报错形态——函数/实例 →
      `TypeError: issubclass() arg 1 must be a class`；非 `BaseWorker` 子类 →
      `Must inherit from BaseWorker: ...`；需带参构造的子类 →
      `requires constructor arguments ... use register_instance or register_factory instead`
      （验证：三条报错文本与源码一致，且给出一条"改对了就不会红"的正例）
- [x] 2.3 与 `CLAUDE.md` 分清受众：首段声明本文件讲"**用这个库写代码**"，`CLAUDE.md` 讲
      "**在这个仓库里改代码**"
      （验证：首段含分工声明；两文件的核心测试命令一致不冲突）

## 3. README FAQ（issue 第 3 条）

- [x] 3.1 `README.md` 新增 `## FAQ`（置于 Contributing 之后、License 之前）：≥10 组
      **自然语言问句** + 每组 1–3 行短答，覆盖 issue 点名的全部主题——不装 broker 能否跑定时
      任务 / 与 Celery 的区别与选型 / 与 APScheduler 的区别 / 多进程与跨机器 / cron 表达式 /
      任务卡住是否被强杀 / 重启后状态是否恢复 / 为什么叫 Zoo 与名字对应 / 与 AI Agent 的关系 /
      生产环境使用情况
      （验证：问句数 ≥10；每个主题都能匹配到至少一问）
- [x] 3.2 `README.zh.md` 新增同构中文 FAQ（同位置、同顺序）：两份 FAQ 的**问句数与主题命中
      集合一致**，各自本地化而非互译粘贴
      （验证：断言比对两份的问句数与主题集合）
- [x] 3.3 每组短答末给出 `docs/FAQ.md` 的绝对链接作为详版；「生产环境有人用吗」按
      `ADOPTERS.md` 如实回答（目前无可核实的第三方使用者）
      （验证：短答不声称未证实的使用者；链接指向 dev blob 且实测 200）

## 4. 站点根发布 `llms.txt`（design D4 / D5）

- [x] 4.1 `scripts/mkdocs_hooks.py` 的复制清单显式化：`.well-known/` 目录 + 根 `llms.txt` 文件，
      逐项"源缺失即构建失败"；复制保持字节一致
      （验证：临时移走 `llms.txt` 时构建失败、移回后构建成功且 `site/llms.txt` 与真源 md5 一致；
      `.well-known/` 的既有语义不变）
- [x] 4.2 `.github/workflows/docs.yml` 的触发路径补 `llms.txt`
      （验证：该文件的 `paths` 含 `llms.txt`；注释说明与 `.well-known/**` 同一理由）

## 5. 机械校验（design D2 / D6）

- [x] 5.1 新增 `tests/test_agent_discoverability.py`，断言至少覆盖：
      ① `llms.txt` 存在且首行 H1、含引用块摘要、含分节标题；
      ② 六类内容与「不要用」三条替代齐备；
      ③ 隐喻声明存在；
      ④ `llms.txt` 中的站点 URL 落在**实测可达白名单**内（写站点子页会红）；
      ⑤ 多进程 / cron / 健康指标三项在 `llms.txt` 里处于**否定**语境（真源取自 README 特性表）；
      ⑥ `AGENTS.md` 四类内容齐备，且其引用的报错串与源码实际 raise 文本一致；
      ⑦ `AGENTS.md` 示例里的导入目标真实可导入；
      ⑧ `AGENTS.md` 含与 `CLAUDE.md` 的分工声明；
      ⑨ 两份 README 的 FAQ 问句数 ≥10、主题命中集合一致；
      ⑩ 每个主题在 `docs/FAQ.md` 中都有对应条目；
      ⑪ FAQ 的"不支持"表述与特性表一致；
      ⑫ 仓库内只有一份手写 `llms.txt`；
      ⑬ mkdocs 构建钩子的复制清单含 `llms.txt`；
      ⑭ `docs.yml` 触发路径含 `llms.txt`
      （验证：`pytest tests/test_agent_discoverability.py` 全绿）
- [x] 5.2 注入违规验证断言有牙齿：串行执行、逐次按 md5 还原，至少
      ① 把 `llms.txt` 的多进程描述改成可用；② 删掉中文 README FAQ 的一个主题问句；
      ③ 把 `AGENTS.md` 的报错串改错一个字符；④ 把 `llms.txt` 的文档站链接改成站点子页；
      ⑤ 从 mkdocs 钩子的复制清单删掉 `llms.txt`；⑥ 从 `docs.yml` 的 `paths` 删掉 `llms.txt`
      （验证：六次注入对应的断言各自变红；还原后文件 md5 与打桩前一致）

## 6. 验证与收尾

- [x] 6.1 外部复核复跑并记录实际输出：`llms.txt` 与 FAQ 里出现的每个绝对 URL 逐个 curl
      （期望：全部 200）
      （验证：结论与本设计 D3 的表一致；若有变化先改文档再提交）
- [x] 6.2 门禁：`ruff check zoo_framework` / `ruff format --check zoo_framework` /
      `mypy zoo_framework` / 全量 `pytest` 不回归（基线 1063 passed）；非 strict
      `mkdocs build` 新增链接告警为 0，且 `site/llms.txt` 存在
      （验证：逐条命令的实际输出）
- [x] 6.3 `openspec validate agent-discoverability --strict` 0 警告；tasks 全勾；
      提交（`Closes #122`）+ 备份与 md5 核对
- [x] 6.4 如实标注生效范围：站点根的 `/llms.txt` 只在合并到默认分支（`main`）后可达——
      本变更只保证构建钩子与部署触发路径就位，SHALL NOT 声称"已生效"
      （验证：设计/文档中的表述与 `#121` 的同一口径一致）
