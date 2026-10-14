# design — native-distribution

## D1 发行形态：选 B（`zoo-framework[native]` 可选附加）

| 形态 | 好处 | 代价 | 结论 |
|---|---|---|---|
| A 独立包 `zoo-framework-native` | 与主包解耦最彻底 | 用户要记住第二个包名，看不出它与框架的关系 | 保留为**底层事实** |
| **B 可选附加 `zoo-framework[native]`** | 用户只多一个方括号；分发只多一条构建矩阵；不装它一切如旧 | 两个包需各自发布 | **采用** |
| C 默认捆绑 | 用户零决策 | 毁掉「纯 Python、零依赖」的卖点 | 不采用 |

B 不是"包装 A"，而是在 A 之上加一层**发现路径**：`zoo-framework-native` 仍是独立 PyPI
项目、独立版本、独立发布工作流；主包只声明
`native = ["zoo-framework-native>=0.1,<0.2"]`。

未安装扩展时的行为沿用既有契约：框架一切如旧，请求原生能力时**显式报错**，不静默回退。

## D2 abi3：`abi3-py311` + 下界 3.11

- 不加 abi3：7 平台 × N 个 Python 版本逐版本发 wheel，且用户的 Python 比 wheel 新就装不上。
- 加 `abi3-py311`：一份 wheel 覆盖 3.11+，wheel 数量减半。
- **必须同时降下界**：下界留在 3.13 时，abi3 覆盖的 3.11/3.12 用户被 `requires-python`
  挡住，等于把收益吃掉。原下界为 3.13 的理由是「没有 CI 覆盖、无法验证在 3.11 上编译」
  ——该理由随本变更的 CI 作业消失（`abi3-load` 在 3.11 上真实加载同一 wheel）。

## D3 CI 用独立工作流，不塞进 tests/quality

- `native.yml` 只在改动 `native/`、`zoo_framework/native/` 或原生相关测试时触发，
  不给主链增加分钟数。
- 关键作业分离：`wheel` 构建**一次**并上传产物，`abi3-load` 下载**同一个产物**在 3.11 与
  3.13 上安装并跑测试。若每个 Python 版本各自构建，「一个 wheel 覆盖多版本」就只是声明
  而不是证据。
- `wheel` 作业断言文件名含 `abi3`：没有该标记时「一份 wheel 覆盖多版本」不成立，
  后续作业也就什么都测不到。

## D4 发布用独立工作流 + 幂等

- `release.yml` 拥有主包的 bump/decide/tag 逻辑，深度耦合三处版本声明；把第二个发行物
  塞进去会让那个文件更难审。原生 wheel 走 `native-release.yml`，同样由 `v*` tag 驱动。
- 原生扩展有**自己的版本**（`native/pyproject.toml`）。框架每次发版都推 tag，若不加保护，
  同一个原生版本会被反复上传并被 PyPI 拒绝——故发布前先查 PyPI，版本已存在则跳过。
- 演练入口：`workflow_dispatch` 默认发 TestPyPI，便于在不污染正式索引的前提下验证链路。

## D5 版本策略：原生版本暂时独立

`native/pyproject.toml` 保持自己的 `version`（当前 0.1.0），不跟随框架版本。理由：扩展的
二进制契约（`CONTRACT_VERSION`）与框架语义版本是两条曲线；跟随会让每次框架补丁发版都
产生一次二进制重发。代价是两处版本号，故 `[native]` 附加用**范围**而不是等号。

## D6 未验证项必须先说

发布链路无法在 PR 内跑通（与 `fix-sbom-out-of-dist` 的 3.6 同一情形）。因此：

- workflow 头部写明 "NOT VERIFIED YET"；
- `native/DECISION.md` 的 5.3 平台表把 Linux/macOS 标为「待 CI 首次运行回填」；
- PR 描述里不得声称发布成功。
