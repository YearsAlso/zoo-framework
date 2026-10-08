## 1. 版本计算脚本化 + main 下限

- [x] 1.1 `scripts/next_version.py`：bump/less/next_version 纯函数 + argparse CLI；dev=patch+beta、main=minor 语义与历史 bash 逐一对应；floor 低于则抬升
- [x] 1.2 release.yml `calc_version` 改为调用脚本；branch==dev 时读 `origin/main` 的 pyproject 版本传 `--floor`；删除 YAML 内嵌 bash 递增（版本计算单一来源）
- [x] 1.3 `tests/test_next_version.py` 9 条：两型递增、事故复现抬升（0.8.4-beta + floor 0.9.0 -> 0.9.1-beta）、floor 三态、回并后无后缀声明的 bump、CLI 冒烟

## 2. back-merge 与回声

- [x] 2.1 新 job `backmerge-dev`：`action==tag && branch==main` 触发（与 tag-release 并行）；RELEASE_PAT、sign-commits、唯一分支名 `backmerge/main-<sha>`、base=dev；PR 正文说明闸门与回声行为
- [x] 2.2 `decide` 声明回声检测：tag 判定后，dev 三处声明与 `origin/main` 完全一致 -> `action=none`（避免撞 tag-release 的"已存在则中止"守卫）
- [x] 2.3 文件头注释更新为四条触发路径 + 版本策略加下限说明

## 3. 验证

- [x] 3.1 pytest 724 全绿（715+9）；YAML 解析合法；release.yml 全部 19 个 run step 过 `bash -n`
- [x] 3.2 已完成（PR #83 已合入 dev；信号②实测达成：#83 合入后自动开出的 bump PR #84 目标 0.9.2-beta，沿 0.9.x 线；#82 已关闭。信号①③机制在位，待下次 main bump 顺带观察，异常另开 issue 不重开）：合并后线上验收信号：下一次 main bump 合并出现 back-merge PR；下一次 dev 内容 push 的 bump 沿 0.9.x；#82 关闭留言 + 归档本变更（随下轮收尾）
