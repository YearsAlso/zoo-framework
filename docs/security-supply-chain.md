# 供应链加固状态 / Supply-chain hardening status

> 这份文档记录 issue #89–#95（CodeQL、token 权限、钉 SHA、Dependabot、依赖漏洞、
> Trusted Publishing + attestation、OpenSSF Best Practices 徽章）的**实际**生效状态。
> 它存在的理由：这些加固此前只写在提交信息与文档里，**没有任何一处记录它们到底生效在哪条
> 分支上**——而"以为做了、其实只在开发线"正是 OpenSSF 评分里最典型的失分点。
>
> 口径：**"生效"以默认分支（`main`）为准**。外部看到的（GitHub 网页、搜索引擎、
> README 上的徽章、Scorecard）都是默认分支。因此每一项都显式标注它的生效范围。

## 1. 状态表

`结论` 取值：**已落地** / **部分落地** / **未做**。`证据` 列要么是仓库内的定位
（`文件:行号`），要么是可复跑的命令（见第 4 节）。

| 项 | 结论 | 生效范围 | 证据 |
|---|---|---|---|
| #89 CodeQL SAST | 已落地 | 默认分支尚未生效（#107） | `.github/workflows/codeql.yml`：`on.push.branches: [main, dev]`（15–18 行）、每周定时 `cron: '0 2 * * 1'`（21 行）、作业级 `security-events: write`（32 行）、`github/codeql-action/init` 与 `/analyze` 均钉 `24c54180…  # v4.38.2`（47、52 行）。`main` 上没有这个文件（`git ls-tree --name-only origin/main .github/workflows/` 里没有 `codeql.yml`） |
| #90 token 权限 | 已落地 | 默认分支尚未生效（#107） | 8 个 workflow **全部**在顶层声明权限：`bench.yml:25`、`build.yml:21`、`codeql.yml:23`、`docs.yml:30`、`quality.yml:14`、`release.yml:60`、`tests.yml:13` 为 `contents: read`，`scorecard.yml:29` 为 `read-all`；写权限只在作业级（`release.yml:157`、`:268`、`:312`、`:415`）。`main` 上 7 个 workflow 只有 3 个有顶层声明（`git grep -n "^permissions:" origin/main -- .github/workflows/`） |
| #91 action 钉 SHA | 已落地（含本次修复） | 默认分支尚未生效（#107） | 全部 `uses:` 均钉 40 位 commit SHA。本次修掉**最后两处**漏项：`release.yml` 原来第 364、384 行的 `actions/checkout@v4` 改为 `11d5960a…  # v4`（与同文件 425 行已在用的 SHA 一致）。复核：`grep -rn "uses: .*@v[0-9]" .github/workflows/` 应无输出。`main` 上全部引用仍是 tag（`git grep -n "uses: " origin/main -- .github/workflows/`） |
| #92 Dependabot | 已落地 | 默认分支尚未生效（#107） | `.github/dependabot.yml`：`github-actions` 每周检查（13–24 行，含小版本分组）与 `pip` 每周检查（25–30 行）。注意 `uv.lock` 的重锁不在 Dependabot 能力范围内，锁文件靠 `uv lock` 手工/CI 维护 |
| #93 依赖漏洞 | 已闭环 | 默认分支尚未生效（#107） | 见第 2 节。锁定集合扫描 0 命中；`main` 上仍在的 `requirements*.txt` 是那 46 条告警的来源 |
| #94 Trusted Publishing + attestation | 已落地 | 默认分支尚未生效（#107） | `release.yml`：作业级 `id-token: write`（416 行）、发布步骤不传 `password`（479–480 行，注释说明为何为空）、SBOM 步骤 `anchore/sbom-action@66cbf4bc…  # v0.24.3`（451–452 行）、keyless 签名 `sigstore/cosign-installer@398d4b0e…  # v3`（464–472 行）、发布作业 `needs: [test, quality]`（408 行）。`gh secret list` 中没有 `PYPI_API_TOKEN`。**公开可核对**：PyPI 对本项目已发布的 wheel 与 sdist 都返回 PEP 740 证明（第 4 节给命令） |
| #95 OpenSSF Best Practices 徽章 | 未做 | 两边都没做 | `bestpractices.dev` 上没有本项目（Scorecard 的 `CII-Best-Practices` 记 0，理由是"no effort to earn an OpenSSF best practices badge"）。这是仓库外的问卷动作，需要维护者本人注册填写，**不能由代码变更代替** |

### 与本变更相关的另外两项

| 项 | 结论 | 生效范围 | 证据 |
|---|---|---|---|
| 支持版本表（#97） | 已落地 | 默认分支尚未生效（#107） | `dev` 的 `SECURITY.md` 已改为不随版本漂移的写法；`main` 上仍写着 `0.5.3-beta` / `0.5.x`（`git show origin/main:SECURITY.md \| sed -n '12p'`）。`main` 的修正属 #107 范围，本变更只验证并加防漂移断言 |
| 自动回并机器人 PR（#82） | 已落地 | 默认分支尚未生效（#107） | `release.yml` 用 `secrets.RELEASE_PAT`（240、276、319、342 行）：`GITHUB_TOKEN` 创建的 PR 不会触发后续 workflow，故这里必须用长期 PAT。这是**有意保留的长期凭据**，不是遗漏——如实记在这里而不是删掉 |

## 2. 依赖漏洞状态（#93）

结论：**开发线已清零**；"46 个已知漏洞"来自**默认分支上 2023 年的依赖清单**。

| 事实 | 证据 |
|---|---|
| 依赖真源唯一 | `pyproject.toml` 的 `[project].dependencies`（60–68 行）：`click`、`pyyaml`、`python-dotenv`、`typing-extensions` |
| 第二份清单已删除 | 仓库内不存在 `requirements*.txt`（PR #100 删除）。**`main` 上它们仍在**：`git ls-tree --name-only origin/main \| grep requirement` → `requirements.txt`、`requirements-dev.txt` |
| 锁文件与声明同源 | `uv.lock`（79 个包），`uv lock --check` 输出 `Resolved 79 packages`（通过） |
| 锁定集合漏洞扫描 | **0 命中**（命令见第 4 节） |
| Rust 探针锁文件 | `bench/pyo3_probe/Cargo.lock`（17 个包）经 OSV 扫描 **0 命中** |
| 46 条的来源 | `main` 上 `requirements.txt` + `requirements-dev.txt` 共 58 条 pin，其中约 34 条命中 OSV 通告：`urllib3 2.0.2` 13 条、`jinja2 3.0.2` 5 条、`virtualenv 20.23.1` 5 条、`requests 2.31.0` 3 条、`filelock 3.12.2` 2 条、`idna 3.4` 2 条，另 `pytest 7.4.3`、`pygments 2.15.1`、`python-dotenv 1.0.0`、`zipp 3.15.0` 各 1 条 |

本次**没有**改动任何依赖版本：需要的是复核（结论：无需刷新），不是刷新。

## 3. 外部审计快照（OpenSSF Scorecard）

采样时间 `2026-10-10T01:54:00Z`，被采样 commit `6ee3944e5566a4184ac12fcab2f51ed5196c60d8`
（即当时的 `main` HEAD），总分 **4 / 10**。

| 检查项 | 分数 | 原因（Scorecard 原文要点） |
|---|---|---|
| Dangerous-Workflow / Maintained / Security-Policy / Binary-Artifacts / License / Packaging | 10 | 无危险工作流模式；90 天内 30 次提交；检出安全策略文件；仓库无二进制；Apache-2.0；经 GitHub Actions 打包发布 |
| CI-Tests | 6 | 16 个已合并 PR 中 10 个有 CI 检查 |
| Code-Review | 0 | `Found 0/16 approved changesets` —— 单人项目，PR 由作者本人合并，无第二人审批（如实记录，不伪造） |
| Token-Permissions | 0 | 被采样 commit 上 7 个 workflow 只有 3 个声明顶层权限；另有 4 条作业级 `contents: write` 告警 |
| Pinned-Dependencies | 0 | 被采样 commit 上全部 action 用 tag 引用 |
| Dependency-Update-Tool | 0 | 被采样 commit 上没有 Dependabot 配置 |
| SAST | 0 | 该 commit 上 `0/30 commits` 经 SAST 检查（无 `codeql.yml`） |
| Signed-Releases | 0 | `v0.10.0`、`v0.9.2-beta` 等发布物未附签名 |
| Vulnerabilities | 0 | 检出 46 条（见第 2 节） |
| CII-Best-Practices | 0 | 未注册 Best Practices 徽章（#95） |
| Fuzzing / Contributors | 0 | 无 fuzz 集成；无第三方贡献组织（如实记录） |
| Branch-Protection | −1 | Scorecard 侧报 `internal error: some github tokens can…`，未能读取分支保护设置；**本表不对分支保护下结论** |
| CI-Tests 的 6 分 | 6 | 具体哪些 PR 未被计入**未逐条核对**，不在此编造原因，列为待查项 |

**剩余扣分项为什么不靠"改分"消除：**

- 六项（Token-Permissions / Pinned-Dependencies / Dependency-Update-Tool / SAST /
  Signed-Releases / Vulnerabilities）的主要成因都是**被采样 commit 落后于开发线**：
  加固已在 `dev` 落地，但默认分支还没拿到。分数变化的唯一路径是 #107 合并。
- Token-Permissions 里剩下的 4 条作业级 `contents: write` 告警对应发布路径里确实需要
  推分支/tag 的作业（`dev` 上为 `release.yml:157`、`:268`、`:312`、`:415`）。这是最小
  必要权限，**不为了刷分删除**；它在默认分支合并后也不会消失。
- `Code-Review`、`Contributors`、`Fuzzing` 是结构性项（需要第二个人、需要外部使用者、
  需要专门的 fuzz 设施），不做无法兑现的承诺。
- `CII-Best-Practices` 需要维护者本人在 `bestpractices.dev` 走一遍问卷（#95）。

## 4. 复核命令

任何人都能复跑下面这些命令核对本表的结论；**结论与本表不一致时，先改本表**。

```bash
# ① 锁定集合的漏洞扫描（Python 依赖）
uv export --format requirements-txt --no-emit-project --no-hashes -o req-audit.tmp.txt
uv run --no-project --with pip-audit pip-audit -r req-audit.tmp.txt --disable-pip --no-deps
rm -f req-audit.tmp.txt          # 期望输出：No known vulnerabilities found

# ② 锁文件与 pyproject 是否同源
uv lock --check                   # 期望输出：Resolved <N> packages（无 "lock file is out of date"）

# ③ Rust 探针锁文件的 OSV 批量查询（bench/pyo3_probe/Cargo.lock）
python - <<'PY'
import json, re, urllib.request
pkgs = re.findall(r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"',
                  open("bench/pyo3_probe/Cargo.lock", encoding="utf-8").read())
req = urllib.request.Request("https://api.osv.dev/v1/querybatch",
    data=json.dumps({"queries": [{"package": {"name": n, "ecosystem": "crates.io"},
                                  "version": v} for n, v in pkgs]}).encode(),
    headers={"Content-Type": "application/json"})
hits = [(n, x["id"]) for (n, _), r in zip(pkgs, json.load(urllib.request.urlopen(req))["results"])
        for x in r.get("vulns", [])]
print("Cargo.lock 包数:", len(pkgs), "命中:", hits)   # 期望：命中 []
PY

# ④ 已发布产物是否带来源证明（PEP 740；把 <版本>/<文件名> 换成 PyPI 上的实际值）
curl -s -o /dev/null -w "%{http_code}\n" \
  "https://pypi.org/integrity/zoo-framework/0.10.0/zoo_framework-0.10.0-py3-none-any.whl/provenance"
                                  # 期望：200（sdist 同理）

# ⑤ 外部评分快照（每周六 01:30 UTC 由 scorecard.yml 重采样）
curl -s https://api.securityscorecards.dev/projects/github.com/YearsAlso/zoo-framework
```

## 5. 默认分支与开发线的差异（#107）

| 事实 | 值 |
|---|---|
| `main` 落后 `dev` | 88 个提交 |
| `.github/` 的差异 | 8 个文件，+226 / −55 |
| `main` 的 workflow | 7 个（无 `codeql.yml`），只有 3 个声明顶层权限，全部 action 用 tag |
| `main` 的依赖清单 | 仍带 `requirements.txt`、`requirements-dev.txt` |
| `main` 的 `SECURITY.md` | 支持版本表仍写 `0.5.3-beta` / `0.5.x` |

这些都不是本仓库"没做"，而是**做了但没到默认分支**。修正路径是 #107（该 issue 要求先在
"回并文档提交 / 更换默认分支 / 自动回并"三种策略里选定一种），本变更不越权替它决定。

## 6. 维护口径

- 每次发布后、或每次 Scorecard 重采样（每周六）后更新第 3 节的快照：采样时间、被采样
  commit、总分。
- 检查项集合发生变化（Scorecard 增删检查项）时，同步更新第 3 节的表。
- 第 1 节的"生效范围"列在 #107 合并后需要整体更新一次——那正是本表存在的意义：
  **让"哪些只在开发线"这件事可见**，而不是靠记忆。
