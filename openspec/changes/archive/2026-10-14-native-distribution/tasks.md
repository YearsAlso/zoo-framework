# tasks — native-distribution

## 1. 规格（spec-first）

- [x] 1.1 `specs/ci-and-packaging/spec.md` 写入 ADDED Requirement：原生扩展 MUST 由 CI
      构建、测试并发布，wheel MUST 为 abi3
- [x] 1.2 `openspec validate native-distribution --strict` 通过

## 2. 实现

- [x] 2.1 `native/Cargo.toml`：pyo3 features 加 `abi3-py311`；更正「与 bench/pyo3_probe
      同版本带」的旧注释（probe 已独立升到 0.29）
- [x] 2.2 `native/pyproject.toml`：`requires-python` 由 `>=3.13` 降到 `>=3.11`，
      并把原注释（「没有 CI 覆盖」）改写为新依据
- [x] 2.3 `native/.gitignore`：补 `/dist/`
- [x] 2.4 新增 `.github/workflows/native.yml`（三平台 cargo test + abi3 wheel +
      原生 pytest；独立的 abi3 证据作业复用同一 wheel 产物）
- [x] 2.5 新增 `.github/workflows/native-release.yml`（manylinux + macOS + Windows 构建，
      OIDC trusted publishing，TestPyPI 演练入口，版本已发布时幂等跳过）
- [x] 2.6 `pyproject.toml`：新增 `native = ["zoo-framework-native>=0.1,<0.2"]` 可选附加
- [x] 2.7 修 `native-release.yml` 的产物 fan-in：三个构建作业共用产物名**不会**合并成一个
      artifact，publish 端按名字取物因此退化为只拿到其中一个（2026-10-13 的 v0.13.1-beta
      实测 `name=native-wheels` 返回 `total_count=3`，那次只发出 Windows 一个 wheel）。
      改为每作业唯一产物名 + `pattern`/`merge-multiple` 收全场，并加产物登记数闸门

## 3. 验证

- [x] 3.1 本机 `cargo test`：11 passed
- [x] 3.2 本机 `maturin build --release`：产物名含 `cp311-abi3`（abi3 生效）
- [x] 3.3 安装该 wheel 后 `pytest tests/test_native_extension.py
      tests/test_native_task_execution.py` → 44 passed
- [x] 3.4 **CI 三平台首次运行**：`native.yml` 在 `main` 上跑完且全绿（run `38339077692`，
      合并 PR #225）——三平台 `cargo test` + 原生 pytest 六个作业全绿；abi3 证据作业在 3.11
      与 3.13 上加载 `wheel` 作业上传的**同一份** wheel 产物。命令：`gh run view 38339077692 --json jobs`
- [ ] 3.5 **发布链路**：首个 tag（v0.13.1-beta，run 38357074578，2026-10-13）已跑通到
      PyPI——但只发出去了三份 wheel 中的一份（Windows），原因见 2.7，已修（PR #239 已合入 dev）。
      同一次运行也证到了前置条件：项目在索引上不存在时 MUST 先在 PyPI 账号侧登记
      pending publisher（Owner/Repository/Workflow/Environment 四项须逐字对上），
      否则 OIDC 交换被拒为 `invalid-publisher`——前三个 tag 全是这条同样的 annotation。
      **归档时补记（2026-10-14）——三平台 wheel 齐全一项已验证**：修复（PR #239）合入后
      发布 `v0.1.1`，`https://pypi.org/pypi/zoo-framework-native/json` 核验产物为
      **3 份**且平台互不重复：`cp311-abi3-win_amd64` / `cp311-abi3-macosx_11_0_arm64` /
      `cp311-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64`；对照未修复的 `0.1.0`
      只有 1 份（`cp311-abi3-win_amd64`）——即「三份中只上去一份」的症状已消除，
      三平台均已发布。详见 `docs/native-release-runbook.md`
- [ ] 3.7 遗留（本变更不做，见 `docs/native-release-runbook.md`）：**TestPyPI 演练**仍未做。
      它验证的是"发布链路在演练环境上先跑通一次"，与 3.5 的"三平台产物是否齐全"是两件事；
      归档时保持未做状态并留在此处，不因归档而消失
- [x] 3.6 Linux/macOS 收益包络：CI 原生构建已接入并在三平台跑绿（run `38339077692`），但
      `native.yml` **不含 benchmark、不产出性能数字**——故 Linux/macOS 的收益包络**仍未测**，
      已按「CI 已接入，性能形状未测」如实记入 `native/DECISION.md` 5.3（不编造）
