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
- [ ] 3.4 **CI 三平台首次运行**（本 PR 触发 `native.yml`）——证据在 PR 的 checks 上
- [ ] 3.5 **发布链路**：首个 tag（v0.13.1-beta，run 38357074578，2026-10-13）已跑通到
      PyPI——但只发出去了三份 wheel 中的一份（Windows），原因见 2.7，已修。
      同一次运行也证到了前置条件：项目在索引上不存在时 MUST 先在 PyPI 账号侧登记
      pending publisher（Owner/Repository/Workflow/Environment 四项须逐字对上），
      否则 OIDC 交换被拒为 `invalid-publisher`——前三个 tag 全是这条同样的 annotation。
      **仍未验证**：修复后三平台 wheel 是否齐全。`zoo-framework-native` 0.1.0 目前在索引上
      只有 Windows wheel，在修复合并并复跑一次之前不得声称三平台均已发布
- [ ] 3.6 Linux/macOS 的收益包络数字（tasks 5.3）待 CI 原生构建跑过后回填
