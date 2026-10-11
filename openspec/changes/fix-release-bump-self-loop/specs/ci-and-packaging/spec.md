## MODIFIED Requirements

### Requirement: 版本线 MUST 跨分支保持连续

发布自动化计算下一版本时，测试分支（dev）的结果 MUST NOT 低于主干（main）的当前声明——以 main 声明为下限，候选低于下限时以下限为基数按同类型重新递增。主干 bump 合并后，自动化 MUST 向测试分支提出 back-merge PR（经人工批准合并，闸门语义不变），使测试分支的声明跟上主干。测试分支收到与主干声明完全一致的"仅版本声明"推送（back-merge 的回声）时 MUST NOT 触发打 tag——同版本号 tag 已存在于主干，重复尝试只会留下失败。发布节奏本身（dev=patch+beta、main=minor）不因本要求改变。

自动化 MUST NOT 因自身产出的版本号提交再次提出 bump PR（自环防护）：判定"本次推送只改了版本声明"所列举的文件集合、以及"声明回声"所比较的文件集合，SHALL 与版本声明处（`pyproject.toml`、`.env`、`zoo_framework/__init__.py`、`CITATION.cff`）逐项一致，且该一致性 MUST 由机械校验守住。漏列一处会使版本号提交被判成内容推送，版本号只涨不发（dev 上实测 `0.11.3-beta` 一路涨到 `0.11.11-beta`，`v0.11.2-beta` 之后没有任何 tag）；回声清单漏列一处则可能把"仅第四处不同"的推送误判成回声而静默不打 tag。

#### Scenario: 分叉被下限拦截

- **WHEN** 主干声明为 0.9.0 而测试分支仍停在 0.8.4-beta，测试分支触发 bump
- **THEN** 计算结果为 0.9.1-beta（沿主干线续算），MUST NOT 产出 0.8.5-beta 等低于主干的版本

#### Scenario: 主干 bump 后自动提出回并

- **WHEN** 主干的版本号 PR 被合并（仅版本声明变更）
- **THEN** 自动化打 tag 的同时向测试分支开出 back-merge PR；该 PR 仍需人工批准

#### Scenario: 回声不打 tag

- **WHEN** back-merge PR 合入测试分支（其结果与主干声明完全一致、只动了版本声明）
- **THEN** 不创建 tag、不开新的 bump PR；测试分支下一次内容推送从主干线续算

#### Scenario: 版本号提交不自环

- **WHEN** 版本号 PR 被合入测试分支（提交只含 `pyproject.toml`、`.env`、`zoo_framework/__init__.py`、`CITATION.cff` 四处版本声明）
- **THEN** 该次推送判定为打 tag，MUST NOT 再开出一个新的 bump PR
- **AND** 该判定所列举的文件集合与四处版本声明逐项一致（由机械校验守住）
