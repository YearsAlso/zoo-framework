# governance-files 任务清单

## 1. `.well-known/security.txt`（issue #120 第 1 条）

- [ ] 1.1 新增仓库根 `.well-known/security.txt`：`Contact`（GitHub 私密通告 URL +
      邮箱，取自 `SECURITY.md` 第 1/2 条）、`Expires`（写入日 +1 年内）、
      `Canonical`（Pages 上的最终 URL）、`Policy`（本仓 `SECURITY.md`）、
      `Preferred-Languages`
      （验证：五字段齐备；`Contact` 每条渠道都能在 `SECURITY.md` 中逐字找到）
- [ ] 1.2 `docs/` 下**不**放副本；`docs/.well-known/` 不存在
      （验证：仓库内检索 `security.txt` 只有根目录一份手写真源）

## 2. Pages 可达机制（issue 第 1 条"注意"段，design D1 方案 A）

- [ ] 2.1 新增 `scripts/mkdocs_hooks.py`：`on_post_build(config)` 把根目录
      `.well-known/` 复制到 `Path(config['site_dir'])/'.well-known'`；
      **真源缺失即 raise**（不静默跳过）
      （验证：函数在临时 site_dir 下产出同名文件；真源缺失时抛异常）
- [ ] 2.2 `mkdocs.yml` 声明 `hooks: [scripts/mkdocs_hooks.py]` 并注明理由
      （验证：yaml 合法；本地 `mkdocs build` 后 `site/.well-known/security.txt`
      存在且与根文件逐字节一致）
- [ ] 2.3 `.github/workflows/docs.yml` 的 `on.push.paths` 补 `.well-known/**`
      （验证：paths 列表含该条目；只改该文件也会触发部署）

## 3. 治理文件（issue 第 2/3/4 条）

- [ ] 3.1 新增 `GOVERNANCE.md`：单人维护现状 + 决策方式 + 成为共同维护者路径 +
      冲突解决 + 版本与破坏性变更承诺（指向 `docs/VERSION_POLICY.md` /
      `docs/MIGRATION.md`，不重述）；维护者名单指向 `MAINTAINERS.md`
      （验证：无"技术委员会/TSC/章程/选举"字样；人数与 `MAINTAINERS.md` 一致）
- [ ] 3.2 新增 `MAINTAINERS.md`：维护者列表 + 安全／发布／文档三类负责人 +
      各类响应时间下界（写成尽力目标；安全项不宽于 `SECURITY.md` 的 48h/7d）
      （验证：三类事项各有条目与下界；与 `SECURITY.md` 时限不冲突）
- [ ] 3.3 新增 `ADOPTERS.md`：邀请句结构 + 两条如实条目（私有项目＝不可核实、
      `zoo-code-agent`＝可核实但属维护者自己的验证消费者，附 `pyproject.toml`
      依赖声明依据）+ 与 `docs/FAQ.md` 相同的"无第三方使用者"结论
      （验证：每条目带可核实／不可核实标注；无编造使用者）

## 4. 行为准则处置（issue 第 5 条，design D2）

- [ ] 4.1 新增迁移 issue（"CODE_OF_CONDUCT.md 迁移到 Contributor Covenant 3.0"，
      含官方仓依据与 v3.0 的结构差异），并把编号回填到 `CODE_OF_CONDUCT.md`
      与 design D2 的占位处
      （验证：CoC 与 design 中无未替换占位符；issue 号可在 GitHub 打开）
- [ ] 4.2 `CODE_OF_CONDUCT.md` 顶部如实披露版本状态：依据 v2.1、官方当前为 v3.0、
      迁移跟踪于该 issue（中英两份一致）
      （验证：无"已采用当前最新版本"式表述）
- [ ] 4.3 补齐举报路由：邮箱 + `[Code of Conduct]` 主题前缀 + 平台级走 GitHub
      Report abuse；显式说明与安全漏洞报送（GitHub 私密安全通告优先）不同；
      保留单人项目无法提供独立第三方受理的说明
      （验证：中英两份一致；无 `[TODO]` 类占位符）

## 5. README 治理入口（issue 第 6 条）

- [ ] 5.1 `README.md` 与 `README.zh.md` 各增「治理与规范」小节，链到
      `GOVERNANCE.md` / `MAINTAINERS.md` / `ADOPTERS.md` / `SECURITY.md` /
      `CODE_OF_CONDUCT.md` / `CONTRIBUTING.md` / `.well-known/security.txt`
      （验证：两份小节的链接目标集合相同；目标文件都存在；
      `docs/FAQ.md` 既有的 `ADOPTERS.md` 引用不再悬空）

## 6. 机械校验（design D5）

- [ ] 6.1 新增 `tests/test_governance_consistency.py`，覆盖 D5 表的八组断言
      （字段与效期、渠道一致、引用存在、两份 README 链接集合、GOVERNANCE 无模板
      机构且人数一致、ADOPTERS 标注、可达性机制三件套、钩子函数行为）
      （验证：`pytest tests/test_governance_consistency.py` 全绿）
- [ ] 6.2 注入违规验证断言有牙齿：分别改掉 `SECURITY.md` 的邮箱、删掉 `docs.yml`
      的 `.well-known/**` 触发项、把 `ADOPTERS.md` 条目标注去掉 → 对应断言变红，
      随后按 md5 逐字节还原
      （验证：三次注入各自变红；还原后 md5 与打桩前一致）

## 7. 验证与收尾

- [ ] 7.1 本地真实构建：`mkdocs build`（非 strict，见既有构建口径）后断言
      `site/.well-known/security.txt` 与根文件逐字节一致；`git status` 不出现
      `site/`；新增链接告警为 0
      （验证：构建日志与产物比对留痕）
- [ ] 7.2 门禁：`ruff check` / `ruff format --check` / `mypy` / 全量 `pytest`
      不回归（基线 1029 passed）
      （验证：四条命令输出留痕）
- [ ] 7.3 `openspec validate governance-files --strict` 0 警告；tasks 全勾；
      提交（`Closes #120`）+ 备份与 md5 核对
