# tasks — native-task-sdk

## 1. 规格（spec-first）

- [x] 1.1 `specs/native-task-execution/spec.md` 写入 ADDED Requirement：契约 MUST 公开
      且可机械校验
- [x] 1.2 `openspec validate native-task-sdk --strict` 通过

## 2. 实现

- [x] 2.1 `docs/native-tasks.md`：四个入口 / 三族错误 / `panic = "unwind"` 纪律 /
      执行纪律 / 演进规则 / 判断表
- [x] 2.2 `native/template/`：最小任务 crate（`example.sum_bytes`），含 3 个 `cargo test`
- [x] 2.3 `native/validate_contract.py`：构建 → 导入 → 逐条核对四条纪律；`--expect-fail`
      用于负例演示
- [x] 2.4 `native.yml`：模板 `cargo test` + 校验器正例（负例不进 CI，见 design 说明）
- [x] 2.5 README 中英两份与 `docs/api/native.md` 标出扩展路径

## 3. 验证

- [x] 3.1 模板 `cargo test`：3 passed
- [x] 3.2 校验器正例：`native/template` → 「契约校验通过」，退出码 0
- [x] 3.3 校验器负例：把副本的 `CONTRACT_VERSION` 改成 99 → 报
      「contract_version() = 99，框架的 CONTRACT_VERSION = 1」，`--expect-fail` 退出码 0
- [x] 3.4 `pytest`（文档一致性与全量）与 `mkdocs build --strict` 通过
- [x] 3.5 CI 三平台上的模板 `cargo test` + 校验器正例：`native.yml` 在 `main` 上全绿（run
      `38339077692`）——ubuntu/macos/windows 三个作业里的「模板 crate 的 cargo test」与
      「契约校验器对模板的机械校验」均为 `success`。命令：`gh run view 38339077692 --json jobs`
