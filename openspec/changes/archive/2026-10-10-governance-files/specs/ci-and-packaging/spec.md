# Spec Deltas: ci-and-packaging

## ADDED Requirements

### Requirement: 文档站产物 MUST 发布 `.well-known/security.txt`

仓库根 `.well-known/security.txt` SHALL 是该文件的唯一手写真源；仓库内 SHALL NOT
存在第二份手写副本（`docs/` 下不放副本），以免两份内容漂移。

文档站构建 SHALL 把该文件复制到站点产物的 `.well-known/security.txt` 路径，
使 `https://yearsalso.github.io/zoo-framework/.well-known/security.txt` 可达。

> 背景（实测）：mkdocs 会忽略点开头的目录——把文件放在 `docs/.well-known/` 后构建，
> `site/.well-known/` 不产生。因此"在 `docs/` 里放一份"既不可达，又制造第二份副本。

源文件缺失时构建 SHALL 失败，SHALL NOT 静默产出不含该文件的站点。

文档部署工作流的触发路径 SHALL 覆盖 `.well-known/**`——否则单独更新 `Expires`
不会触发重新发布，已发布站点会带着过期文件。

#### Scenario: 构建产物含该文件且与真源逐字节一致

- **WHEN** 执行文档站构建
- **THEN** 产物目录下存在 `.well-known/security.txt`
- **AND** 其内容与仓库根 `.well-known/security.txt` 逐字节一致

#### Scenario: 真源缺失时构建失败

- **WHEN** 仓库根 `.well-known/security.txt` 不存在而构建被触发
- **THEN** 构建以失败结束并指出缺失的源文件
- **AND** 不产出缺少该文件的站点产物

#### Scenario: 触发路径覆盖真源

- **WHEN** 检查文档部署工作流的触发条件
- **THEN** 触发路径包含 `.well-known/**`
- **AND** 因此仅修改该文件也会重新构建并部署

#### Scenario: 不存在第二份手写副本

- **WHEN** 在仓库内检索 `security.txt` 的手写副本
- **THEN** 只有仓库根一份真源
- **AND** `docs/` 下不含 `.well-known/security.txt`（该副本既不可达又会导致漂移）
