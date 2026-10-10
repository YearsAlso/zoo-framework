# Spec Deltas: ci-and-packaging

## ADDED Requirements

### Requirement: 文档站产物 MUST 发布仓库根 `llms.txt`

仓库根 `llms.txt` SHALL 是该文件的唯一手写真源；仓库内 SHALL NOT 存在第二份手写副本。

文档站构建 SHALL 把该文件复制到站点产物的**根路径**，使
`https://yearsalso.github.io/zoo-framework/llms.txt` 可达——`llms.txt` 的约定位置正是站点根，
只放在仓库里、取不到该 URL，本要求的发现性目的即落空。

站点产物中的该文件 SHALL 与仓库根真源逐字节一致。

源文件缺失时构建 SHALL 失败，SHALL NOT 静默产出一个不含该文件的站点。

文档部署工作流的触发路径 SHALL 覆盖 `llms.txt`——否则单独更新它的内容不会触发重新发布，
已发布站点会一直带着旧版本（既有 `.well-known/**` 出于同一理由已被列入触发路径）。

#### Scenario: 站点根可达且与真源一致

- **WHEN** 完成一次文档站构建
- **THEN** 站点产物根存在 `llms.txt`，且其内容与仓库根真源逐字节一致

#### Scenario: 真源缺失即构建失败

- **WHEN** 仓库根 `llms.txt` 不存在
- **THEN** 构建以失败告终，不产出缺少该文件的站点

#### Scenario: 只改 `llms.txt` 也会重新发布

- **WHEN** 提交中仅 `llms.txt` 发生变化（文档其他路径未变）
- **THEN** 文档部署工作流被触发

#### Scenario: 不产生第二份手写副本

- **WHEN** 检查仓库内 `llms.txt` 的文件数量
- **THEN** 全仓只有仓库根一份（`docs/` 下不放副本），站点侧的那份由构建期复制产生
