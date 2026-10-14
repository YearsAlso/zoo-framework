## Why

在普通目录中运行 `zfc --worker name` 会返回成功并创建 `workers/`，但该文件没有脚手架入口导入或注册，无法被项目使用。调用方得到成功退出码，却留下无效产物。

## What Changes

- 以 `src/main.py` 作为脚手架项目根目录的判据；从当前工作目录向父目录查找最近的项目。
- 找不到项目入口时，在任何文件系统写入之前明确失败，并提示如何创建或进入项目。
- 保持 `zfc --create <name> --worker <worker>` 的组合行为不变，并覆盖从项目子目录调用的路径。
- 更新 CLI 行为规格、README、变更日志及回归测试。

## Capabilities

### Modified Capabilities

- `cli-scaffolding`: Worker 输出必须位于可由项目入口接线的脚手架项目中。

## Impact

- 运行时代码：`zoo_framework/cli/scaffold.py`
- 测试：CLI 合同及跨平台输出目录测试
- 文档与规格：README、CLAUDE.md、CHANGELOG.md、OpenSpec delta
- 无新增依赖。此前在任意目录直接生成 `./workers/` 的调用现在会明确失败。
