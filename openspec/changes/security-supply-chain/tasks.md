# security-supply-chain 任务清单

## 1. #89–#95 实际状态留档（issue 第 2 条）

- [ ] 1.1 新增 `docs/security-supply-chain.md`：#89 CodeQL、#90 token 权限、#91 钉 SHA、
      #92 Dependabot、#93 依赖漏洞、#94 Trusted Publishing + attestation、#95 Best Practices
      徽章逐条给出**结论**（已落地 / 部分落地 / 未做）与**证据**（`.github/...:行号`
      或可复跑命令）。
      证据必须来自本次实测，不得转述旧审计数字：
      ① 顶层 `permissions` 计数（8/8）；② `uses:` 钉 SHA 清单（唯一漏项 = release.yml 的
      两处 `@v4`）；③ `.github/dependabot.yml`、`.github/workflows/codeql.yml` 存在；
      ④ `uv lock --check` 通过；⑤ 对锁定集合的漏洞扫描 0 命中；⑥ `bench/pyo3_probe/Cargo.lock`
      的 OSV 扫描 0 命中；⑦ `gh secret list` 实名（有 `PYPI`、`RELEASE_PAT`，无
      `PYPI_API_TOKEN`）；⑧ PyPI integrity API 对 0.10.0 的 wheel/sdist 均返回 200
      （验证：每行证据列非空且可在仓库内定位；命令类证据给出可复跑的完整命令）
- [ ] 1.2 状态表显式区分生效范围：**只落在 dev** 的项（#89 #90 #91 #92 #94）标注
      "默认分支尚未生效"并指向 #107；#95 标注"未做（仓库外问卷）"；并记录 main↔dev 实测差异
      （`git diff --stat origin/main..HEAD -- .github/` = 8 文件 +226/−55）
      （验证：不存在把仅 dev 生效写进"已生效"的行；文中出现跟踪 issue 编号）
- [ ] 1.3 记录外部审计快照：Scorecard 采样时间 `2026-10-10T01:54:00Z`、被采样 commit
      `6ee3944e5566a4184ac12fcab2f51ed5196c60d8`、总分 4，以及逐项分数与**剩余扣分项原因**
      （含 release.yml 四处 job 级 `contents: write` 是合法需要，不为刷分删除）
      （验证：快照三要素齐备；文内说明"分数是默认分支的快照，本变更不会立刻改变它"）
- [ ] 1.4 `mkdocs.yml` 的 nav 增加「安全」分组，收录 `SECURITY_MODEL.md` 与
      `security-supply-chain.md`
      （验证：nav 含两条；非 strict 构建后两页进入 `site/`）

## 2. 钉 SHA 漏项修复（issue 第 2 条"特别检查"）

- [ ] 2.1 `.github/workflows/release.yml:364` 与 `:384` 的 `actions/checkout@v4` 钉到
      `11d5960a326750d5838078e36cf38b85af677262  # v4`（与同文件 `:425` 已使用的 SHA 一致）
      （验证：`grep -rn "uses: .*@v[0-9]" .github/workflows/` 无输出；两处 diff 仅两行）

## 3. 支持版本表去漂移（issue 第 1 条）

- [ ] 3.1 `SECURITY.md` 中英两份支持表的**举例**去掉版本字面量（当前为 `0.9.x` / `0.8.x`，
      项目已是 `0.10.x`——举例本身已漂移），保留表行数与 ✅/❌ 顺序不变
      （验证：表中除固定边界 `1.0` 外不含 `数字.数字`；双语数据行数一致）
- [ ] 3.2 确认 `SECURITY.md` 不含 `pyproject.toml` 的当前版本串
      （验证：断言通过；`main` 上的陈旧表属 #107，不在本变更修）

## 4. 使用者视角的安全模型文档（issue 第 5 条）

- [ ] 4.1 新增 `docs/SECURITY_MODEL.md`，四节齐备：支持版本策略 / 漏洞报送渠道 /
      依赖策略 / **未做的事**（≥3 条）
      （验证：四节标题存在；"未做的事"至少 3 条列表项）
- [ ] 4.2 "未做的事"包含两类硬事实：尚无**第三方安全审计**；**默认分支上的加固尚未生效**
      （指向 #107）；并如实写明 `RELEASE_PAT` 长期凭据仍在（自动回并机器人 PR 需要）
      （验证：三类表述都在，且与状态表一致）
- [ ] 4.3 依赖策略以可核对事实陈述：运行依赖条数与 `pyproject.toml` 的 `dependencies`
      条数一致、无 broker / 无网络层、锁定集合扫描 0 命中（附复核命令）
      （验证：断言比对条数；命令可复跑）

## 5. 机械校验（design D6）

- [ ] 5.1 新增 `tests/test_security_supply_chain.py`，断言至少覆盖：
      ① 每个 workflow 有顶层 `permissions` 且顶层不含 `write`；
      ② 所有 `uses:` 均钉 40 位 SHA（无 `@vN`）；
      ③ release.yml 的发布作业声明 `id-token: write` 且不传 `password`；
      ④ 存在 SBOM 步骤与 keyless 签名步骤；发布作业 `needs` 含测试与质量；
      ⑤ 仓库内不存在 `requirements*.txt`；
      ⑥ `pyproject.toml` 的每个依赖名都能在 `uv.lock` 中找到；
      ⑦ `SECURITY.md` 支持表无版本字面量（除 `1.0`）且不含当前版本串；双语行数/标记一致；
      ⑧ `docs/SECURITY_MODEL.md` 四节齐备、"未做的事"≥3 条且含第三方审计未做；
      ⑨ 该文档声明的运行依赖条数 = `pyproject.toml` 的 `dependencies` 条数；
      ⑩ `docs/security-supply-chain.md` 中 #89–#95 每行证据列非空；
      ⑪ 该文档含"默认分支尚未生效"标注且不把 dev-only 项写成已生效；
      ⑫ 文档声明的依赖漏洞复核命令存在（可复跑）
      （验证：`pytest tests/test_security_supply_chain.py` 全绿）
- [ ] 5.2 注入违规验证断言有牙齿：串行执行、逐次按 md5 还原，至少
      ① 在 release.yml 里恢复一处 `actions/checkout@v4`；② 从一个 workflow 删掉顶层
      `permissions`；③ 把 `SECURITY.md` 的举例改回 `0.9.x`；④ 删掉
      `docs/security-supply-chain.md` 某行的证据列；⑤ 把状态表中 #89 的生效范围改成"已生效"；
      ⑥ 改 `docs/SECURITY_MODEL.md` 声明的依赖条数
      （验证：六次注入对应的断言各自变红；还原后文件 md5 与打桩前一致）

## 6. 变更日志（issue 第 3 条）

- [ ] 6.1 `CHANGELOG.md` 的 `## [Unreleased]` 下增 `### Security`：依赖漏洞状态复核结论
      （锁定集合扫描 0 命中；第二份依赖清单已删除）、钉 SHA 漏项修复（#91）、
      新增安全模型与供应链状态文档（#121）
      （验证：段落存在且不含编造的版本刷新动作——本次**未**改动任何依赖版本）

## 7. 验证与收尾

- [ ] 7.1 外部复核命令复跑并记录实际输出：`uv lock --check`、对锁定集合的漏洞扫描
      （`uv export` + `pip-audit -r`）、`bench/pyo3_probe/Cargo.lock` 的 OSV 扫描、
      PyPI integrity API（wheel + sdist）、Scorecard API
      （验证：结论与状态表所记一致；若任一结论变化，先改状态表再提交）
- [ ] 7.2 门禁：`ruff check zoo_framework` / `ruff format --check zoo_framework` /
      `mypy zoo_framework` / 全量 `pytest` 不回归（基线 1044 passed）；`mkdocs build`
      （非 strict，按既有构建口径）新增链接告警为 0
      （验证：逐条命令的实际输出）
- [ ] 7.3 `openspec validate security-supply-chain --strict` 0 警告；tasks 全勾；
      提交（`Closes #121`）+ 备份与 md5 核对
