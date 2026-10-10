# branch-doc-sync 提案

## Why

`main` 是仓库默认分支（GitHub 网页、搜索引擎、外部链接的默认入口），但落后 `dev` 29 个提交（反向 3 个，文档类差异约 1574 行插入）。issue #97 已在 dev 上把 `SECURITY.md` 的支持版本表改为"不随版本漂移"的写法，但 `main` 上的 `SECURITY.md` 仍声明 `0.5.3-beta` 并按 "latest 0.5.x" 划支持线——项目实际已是 `0.10.2-beta`。结果：**在 dev 上修好的对外文档，访客在 main 上看到的仍是旧错版本**。每次文档修复都靠人工判断"要不要回并 main"，漂移必然复发。

## What Changes

- 新增 `docs/BRANCHING.md`：写清两个分支的职责之外，**必须定义"访客可见性承诺"**——哪些类别的修改（对外文档 README / README.zh / SECURITY / 治理文件）在什么时间窗内必须出现在 main 上，以及验证不再漂移的检查方法。
- 实施所选策略（在 design.md 中评估三案后定，倾向 c：文档/治理类修复回并 main + 机制化回并），本次至少完成：把 dev 上的 `SECURITY.md`（不漂移支持版本表）同步到 `main`，消除 `0.5.3-beta` 残留。
- README / CONTRIBUTING 中指向 `main` 分支内容的表述与分支策略文档互链，避免各自维护。
- 不合并 dev 上尚未发布的功能类差异（README 重写、新增 openspec change 等**必须随各自 change 走正式流程后自然下发**，不在本 change 手动搬运）。

## Capabilities

### New Capabilities

- `branch-visibility`：文档与治理文件在默认分支上的可见性契约——SHALL 定义"哪些文件类别属于访客可见面"、MUST 定义"dev 上的对外文档修复在多长时间内必须可见于 main"、以及验证漂移的检查方法。

### Modified Capabilities

（无——不影响现有 spec 的 REQUIREMENT；`ci-and-packaging` 描述的是 CI 门禁行为，本 change 不改 workflow 门禁。）

## Impact

- 受影响文件：`docs/BRANCHING.md`（新增）、`SECURITY.md`（main 侧同步，dev 侧不动）、`CONTRIBUTING.md`（一小节互链）、`README.md`（提及分支策略处互链，中文半同步）。
- 不改 `.github/workflows/*` 的门禁行为；如采用 c 案的自动回并，仅新增一个独立 workflow（改动风险高时在 design.md 降级为"文档化人工流程 + 检查清单"）。
- 不影响产品代码、API、依赖。
- 跨平台影响：无（纯仓库治理）。
- 关联 issue：#107（本 change 的工作单）。
