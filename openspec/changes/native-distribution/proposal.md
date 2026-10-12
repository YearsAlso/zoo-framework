# 提案：native-distribution —— 把原生扩展变成可安装、可验证的交付物

## Why

`native/DECISION.md` 已给出 go 结论（Modbus RTU 帧解析在包络内端到端 1.57x–9.63x），
但实测状态是：`.github/workflows/` 下**没有任何** workflow 构建或测试 `native/`；
`native/Cargo.toml` 未启用 abi3；`https://pypi.org/pypi/zoo-framework-native/json`
返回 **404**。也就是说 **go 结论只存在于测量报告里，没有存在于任何可安装产物里**
（issue #129）。

同时 `native/pyproject.toml` 的 `requires-python = ">=3.13"` 会把 abi3 的收益吃掉：
abi3 的意义是「一份 wheel 覆盖 3.11+」，而下界把 3.11/3.12 用户挡在门外。

## What Changes

- **启用 abi3**：`pyo3` 的 features 加 `abi3-py311`，`requires-python` 由 `>=3.13`
  降到 `>=3.11`（两者必须同改，否则收益被自己的下界吃掉）。
- **新增 `native.yml`**：三平台 `cargo test` + 构建 abi3 wheel + 安装后跑原生 pytest；
  另有 abi3 证据作业——**同一个 wheel 产物**在 3.11 与 3.13 上加载。
- **新增 `native-release.yml`**：tag 驱动的 wheel 发布（manylinux + macOS + Windows），
  走 OIDC trusted publishing；提供 TestPyPI 演练入口；版本已发布时幂等跳过。
- **发行形态选 B**：`pip install zoo-framework[native]`——主包只多一个可选附加，
  原生扩展仍是独立发行物（理由见 design.md D1）。
- `native/.gitignore` 补 `/dist/`（maturin 的 wheel 产物不入库）。

## Non-Goals

- 不改原生任务契约与 API 语义。
- 不把原生扩展做成默认捆绑（那会毁掉「纯 Python、零依赖、无 broker」的核心卖点）。
- 不升级 pyo3 版本带（0.23 的边界行为已实测；升级是 #205 的独立变更）。
- 不改 `release.yml` 的主包发布逻辑。

## Impact

- `native/Cargo.toml`、`native/pyproject.toml`、`native/.gitignore`、`native/DECISION.md`
- 新增 `.github/workflows/native.yml`、`.github/workflows/native-release.yml`
- `pyproject.toml`：新增 `native` 可选附加

**未完成（如实说明）**：`native-release.yml` 的发布链路**无法在本变更内验证**——它的真实
证据只在第一个 tag（或一次 TestPyPI 演练）之后才存在。Linux/macOS 的包络数字同样要等
CI 原生构建跑过一次才能回填。
