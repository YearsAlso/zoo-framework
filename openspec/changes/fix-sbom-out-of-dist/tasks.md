# tasks — fix-sbom-out-of-dist

## 1. 规格（spec-first）

- [x] 1.1 `specs/ci-and-packaging/spec.md` 写入 MODIFIED Requirement：SBOM 产物 MUST 落在
      `packages-dir`（`dist/`）之外，Scenario THEN 指向 `dist-sbom/`
- [x] 1.2 `openspec validate fix-sbom-out-of-dist --strict` 通过（输出：Change
      'fix-sbom-out-of-dist' is valid）

## 2. 实现

- [x] 2.1 `release.yml` 新增 SBOM 输出目录准备步骤（`mkdir -p dist-sbom`，与签名步骤的
      `mkdir -p dist-signatures` 同形）
- [x] 2.2 `release.yml` 的 SBOM `output-file` 改为 `dist-sbom/sbom.spdx.json`
- [x] 2.3 `release.yml` 的 release 附件 glob 改为 `dist-sbom/*.spdx.json`
- [x] 2.4 更新 SBOM 步骤上方注释：写明「扫描 `dist/`、产物 MUST 在 `dist/` 之外」的根因
      与实测证据（v0.11.1-beta / v0.11.2-beta）
- [x] 2.5 补机械校验：`tests/test_security_supply_chain.py` 新增
      `test_non_distribution_artifacts_stay_out_of_the_upload_directory`——断言 SBOM 落点
      不在 `dist/`、输出目录已 `mkdir`、附件列表中 `dist/` 内只有 wheel/sdist

## 3. 验证

- [x] 3.1 静态核对 `release.yml` 中所有 `dist/` 路径：写入只有 `python -m build`（wheel
      与 sdist），其余是扫描目标（`path: dist/`）、只读取的签名循环与 `ls`；无第三类写入
- [x] 3.2 全仓无遗留引用：`git grep "dist/sbom"` 为空、`git grep "dist/\*\.spdx"` 只命中
      `openspec/changes/archive/2026-10-10-packaging-standards/`（归档历史，按 SDD 不得改）
- [x] 3.3 YAML 语法：`check-yaml`（pre-commit）对 `release.yml` 通过
- [x] 3.4 断言"有牙齿"：注入 3 个违规实现（SBOM 写回 `dist/`、附件 glob 指回 `dist/`、
      删掉 `mkdir -p dist-sbom`）逐个确认该用例变红，再按 md5 逐字节还原
      （`md5=35a50ee01ac72ae18ebc4eb0b5262a45`，还原后复跑通过）
- [x] 3.5 用例：`pytest tests/test_security_supply_chain.py -q` → 20 passed
- [ ] 3.6 **发布链路的真实验证只能等下一个 tag**：本变更无法在 PR 内跑通
      `Publish to PyPI`。dev 上本推送会触发一次 patch 版本 PR，其合并产生的 tag 将首次
      以新路径走完整条发布链路——在那之前**不得声称已验证发布成功**
