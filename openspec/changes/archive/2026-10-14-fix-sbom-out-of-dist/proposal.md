# 提案：fix-sbom-out-of-dist —— SBOM 产物移出 PyPI 上传目录

## Why

`release.yml` 把 SBOM 写到 `dist/`，而发布步骤 `pypa/gh-action-pypi-publish` 会把
`packages-dir`（默认 `dist/`）下的**每个文件**当作分发包校验。SBOM 因此让整个发布中止：
dev 的 tag `v0.11.1-beta` 与 `v0.11.2-beta` 两次发布都死在 `Publish to PyPI`，日志为

```
Checking dist/sbom.spdx.json: ERROR   InvalidDistribution: Unknown distribution format: 'sbom.spdx.json'
```

这不是本次合并引入的问题，而是 `packaging-standards`（#119）引入 SBOM 时就埋下、直到
首次打 tag 才暴露的缺陷。main 上的 `57bb4cd` 已用同一手法修掉签名（`.pem` / `.sig` 移入
`dist-signatures/`）——SBOM 是同一根因下未被覆盖的那一个，且它比签名更早被上传工具扫到
（按文件名序在 wheel 之前），所以先中止的就是它。

权威规格 `ci-and-packaging` 的 Scenario 目前把 SBOM 钉在 `dist/`（"`dist/` 中出现 SBOM
文件"），与「发布 MUST 成功」直接冲突，故本变更同时修正规格。

## What Changes

- SBOM 产物改写到 `dist-sbom/`；**扫描目标仍是 `dist/`**（SBOM 描述的是即将发布的分发包）。
- release 附件列表由 `dist/*.spdx.json` 改为 `dist-sbom/*.spdx.json`。
- 规格 `ci-and-packaging` 的 MODIFIED Requirement：SBOM 产物 MUST 落在 `packages-dir`
  之外；Scenario 的 THEN 由 `dist/` 改为 `dist-sbom/`，并补一条「`dist/` 中只有 wheel
  与 sdist」的断言。

## Non-Goals

- 不改 SBOM 的生成工具（`anchore/sbom-action` / Syft）、格式（SPDX-JSON）与「生成失败即
  工作流失败」的既有纪律（不加 `continue-on-error`）。
- 不改签名产物位置（`dist-signatures/`）与 cosign keyless 的实现。
- 不改 wheel / sdist 的构建路径，不改 PyPI 的 trusted publishing（OIDC）配置。
- 不引入新的第三方 action 或依赖。

## Impact

- `.github/workflows/release.yml`：SBOM 输出目录准备步骤 1 个，`output-file` 与附件 glob
  各 1 行，步骤注释补充根因。
- `openspec/specs/ci-and-packaging/spec.md`：1 个 Requirement（1 条 Scenario 变更 + 1 条
  断言新增）。
- 前置依赖：`57bb4cd`（签名移出 `dist/`）已在当前分支上——本变更与它同根因、同手法。
