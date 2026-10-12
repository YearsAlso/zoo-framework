# 提案：native-task-sdk —— 把原生任务注册表做成公开的 SDK

## Why

`native/` 已有契约版本机制、任务注册表、能力清单与实测方法论，但**没有任何东西让第三方
照着写一个原生任务**：没有公开契约文档、没有模板、没有校验器、没有"我的任务值不值得
下沉"的判断表（issue #139）。

这条路径的特别之处在于：它的贡献门槛是**技术性的**（会写 Rust 并遵守契约），
**不需要先有用户**——是生态里唯一不依赖"先信任一个 0-star 框架"的扩展槽位。

## What Changes

- 新增 `docs/native-tasks.md`：四个入口的形状、三族错误的边界、`panic = "unwind"` 纪律、
  执行纪律、契约演进规则、**「该不该下沉」判断表**（每条附实测数字）。
- 新增 `native/template/`：最小可用的原生任务 crate（含 `cargo test`，3 个用例）。
- 新增 `native/validate_contract.py`：契约校验器——`cargo build --release` 后导入产物，
  逐条核对四条纪律，退出码 0/1；带 `--expect-fail` 用于演示"故意写错的 crate 会被报错"。
- `native.yml` 增加两步门禁：模板的 `cargo test`、校验器对模板的机械校验。
- README（中英）与 `docs/api/native.md` 标出这条扩展路径。

## Non-Goals

- 不建插件市场、不做插件注册中心。
- 不改四个入口的既有语义（只公开与工具化）。
- 不承诺原生任务的性能数字（沿用"带工作包络"的诚实口径）。
- 不把校验器接进默认 pytest 套件：它需要 Rust 工具链与一次 release 构建，属于
  `native.yml` 的门禁，不是单测。

## Impact

- 新增：`docs/native-tasks.md`、`native/template/**`、`native/validate_contract.py`
- 修改：`.github/workflows/native.yml`、`README.md`、`README.zh.md`、`docs/api/native.md`
- 前置：#129（原生扩展的 CI / abi3 / wheel）——第三方不可能为一个装不上的扩展写任务。
