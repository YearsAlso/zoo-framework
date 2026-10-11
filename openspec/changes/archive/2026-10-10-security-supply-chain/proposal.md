## Why

issue #89–#95 做了九项供应链加固（CodeQL、token 权限、钉 SHA、Dependabot、依赖漏洞、
Trusted Publishing、best-practices 徽章…），但**没有任何一处记录它们的实际生效状态**，
而且实测发现三类问题：

- **以为做了、其实没做全**：全部 workflow 都声明了顶层 `permissions`（8/8），但
  `release.yml:364` 与 `:384` 的 `actions/checkout@v4` **没钉 SHA** —— 其余 action 都钉了，
  只有这两处漏网。"钉 SHA"是一项要么全做要么不算做的检查。
- **"生效"的定义被默认分支偷换**：上述加固全部只在 `dev`。默认分支 `main` 落后 88 个提交，
  其 7 个 workflow 里 3 个有顶层 `permissions`、全部 action 用 tag、没有 `codeql.yml`、
  没有 `dependabot.yml`，且仍带着 2023 年的 `requirements*.txt`。OpenSSF Scorecard 在
  `main` HEAD（`6ee3944`，2026-10-10T01:54Z 采样）上给 **4/10**：Token-Permissions 0、
  Pinned-Dependencies 0、Dependency-Update-Tool 0、SAST 0、Signed-Releases 0、
  Vulnerabilities 0（46 条）。**外部世界看到的仍然是一个没做过加固的仓库。**
- **对使用者没有一份可读的安全说明**：`SECURITY.md` 讲报送与信任边界，
  `docs/` 下没有任何一页说明"支持哪些版本、依赖策略是什么、我们**没做**什么"。

## What Changes

- **新增 `docs/security-supply-chain.md`（入站点点 nav）**：#89–#95 的实际状态表，
  每条给出**文件路径 + 关键行**；显式区分「dev 已落地」与「默认分支尚未生效」，
  并记录 Scorecard 的实测分数与逐项理由（含 4 条 job 级 `contents: write` warn ——
  那些 job 确实要推分支/tag，不为了刷分去掉）。
- **修复唯一的钉 SHA 漏项**：`release.yml:364` / `:384` 的 `actions/checkout@v4` 钉到
  commit SHA，与其余 17 处保持一致。
- **新增 `docs/SECURITY_MODEL.md`（入 nav）**：给使用者看的安全说明 —— 支持版本策略、
  漏洞报送渠道、**可验证的**依赖策略事实（运行依赖 4 个、无网络 broker、锁定集合
  漏洞扫描为 0），以及**未做的事**（无第三方安全审计、未注册 OpenSSF Best Practices
  徽章 #95、默认分支加固未生效 #107、`RELEASE_PAT` 仍是长期凭据）。
- **`SECURITY.md` 支持版本表去漂移**：dev 的表已改成"最新 minor 线"写法（#97 已关闭），
  但表内举例仍是 `0.9.x` / `0.8.x`（当前已是 `0.10.x`）—— 示例本身已经漂移。改为不含
  具体版本号的写法，并新增机械断言把它锁死（含"不得出现 `pyproject.toml` 的当前版本号"）。
- **机械校验**：新增 `tests/test_security_supply_chain.py`，把"钉 SHA、显式权限、
  OIDC 发布、锁文件与 pyproject 同源、版本表不漂移、状态表与实况一致"变成 CI 能拦的断言。

## Capabilities

### New Capabilities

- `security-model`: 面向使用者的安全模型与供应链加固状态（支持版本策略、报送渠道、
  依赖策略、未做的事、#89–#95 状态表），以及"支持版本表不随版本号漂移"的约束。

### Modified Capabilities

- `ci-and-packaging`: 新增两条要求 —— ①工作流 MUST 显式声明顶层最小权限、MUST 把每个
  `uses:` 钉到 commit SHA、发布 MUST 走 OIDC 短期令牌而非长期 token；②依赖漏洞状态
  MUST 可复现复核（唯一真源 + 对锁定集合扫描）。

## Impact

- **新增文件**：`docs/security-supply-chain.md`、`docs/SECURITY_MODEL.md`、
  `tests/test_security_supply_chain.py`。
- **修改文件**：`.github/workflows/release.yml`（2 行钉 SHA）、`SECURITY.md`
  （支持版本表去漂移，中英各一处）、`mkdocs.yml`（nav 两行）。
- **不改**：`main` 分支与发版流程（`SECURITY.md` 在 `main` 上的陈旧表属 #107 范围，
  本次只验证并如实记录）；不新增第三方依赖；不改任何 `zoo_framework/` 运行时行为。
- **风险**：`release.yml` 的改动只在 tag 推送时才会执行，本地只能做静态校验；
  钉的是 `actions/checkout` 官方仓的既有 SHA（与同文件 `:425` 已在用的 v4 SHA 一致）。
