## Why

issue #82：`release.yml` 的版本自动化**按各自分支的声明独立算版本**，main 的 bump 从不回流 dev。已实际咬过：10-06 main 升到 0.9.0（tag + PyPI latest）后，dev 沿 0.8.x-beta 旧线于 10-07 自动连发 `0.8.3-beta` / `0.8.4-beta`（tag + PyPI 占号，版本号永久作废），且 dev 的 `0.8.4` 声明随时可能在下次 dev→main 合并时把版本倒挂带回 main。#76 人工回并修的是现象，机制未变——main 下次升 stable 会原样再犯。

## What Changes

按维护者裁定的**双保险形状**（自动回并 + main 下限）：

- **版本计算脚本化 + 下限抬升**：YAML 内嵌 bash 递增逻辑收敛为 `scripts/next_version.py`（纯函数 + argparse CLI，可被 pytest 覆盖——bash 内嵌形态是分叉能长期存活的原因之一，无法被测）；dev 计算时传入 main 当前声明作 `floor`，候选低于 floor 就以 floor 为基数重新递增。**即使回并 PR 被漏合，也算不出低于 main 的版本**。main 自身不需下限；发布节奏（dev=patch-beta、main=minor）不变
- **路径 4：main bump 合并后自动向 dev 开 back-merge PR**（新 job `backmerge-dev`，与 tag-release 并行、互不依赖）：RELEASE_PAT + sign-commits + 每轮唯一分支名（`backmerge/main-<sha>`）；PR 正文写明来源与闸门语义（仍需人工批准合并，分支保护不变）
- **声明回声检测**：`decide` 分类新增例外——dev 推送若"只改三处声明"且改完与 `origin/main` 完全一致，判为 back-merge PR 入 dev 的回声，`action=none` 不打 tag（同版本号 tag 已存在于 main，撞上 tag-release 的"已存在则中止"守卫只会留红色失败）。正常 dev bump 后声明必领先 main，此规则不误杀

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `ci-and-packaging`：新增「版本线 MUST 跨分支保持连续」——dev 计算以 main 声明为下限；main bump 后 MUST 自动提出 back-merge PR；回并产生的声明回声 MUST NOT 触发 tag

## Impact

- **代码**：`.github/workflows/release.yml`（头注释、decide 回声检测、calc_version 接脚本、新 job）；新增 `scripts/next_version.py`
- **测试**：`tests/test_next_version.py` 9 条（递增语义两型、事故复现抬升、floor 三态、CLI 冒烟）
- **CI 行为**：下一次 main bump 合并后会多出一个待人工合并的 back-merge PR；下一次 dev push 的 bump 沿 0.9.x 线（当前 floor=0.9.1）
- **issue**：#82 关闭
- **无法本地验证的部分**：workflow 真实触发链只能合并后观察（计划内已注明验收信号）
