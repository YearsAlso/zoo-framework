## 1. 修复

- [x] 1.1 `load_state_machines` 守卫按真实类型分派：ThreadSafeDict 原样恢复 / dict 包装 / 其它 `TypeError`；docstring 改写（裁定整表替换语义，历史缺陷说明保留为溯源）
- [x] 1.2 回归测试 `tests/test_state_restore.py` 6 条：issue 最小复现、dict 兼容、未知类型拒绝、None 语义、worker 真实读盘路径、备份恢复路径

## 2. 验证

- [x] 2.1 全量 pytest 711（705+6）绿、mypy 0 error、ruff/bandit 绿；openspec validate 全绿
- [ ] 2.2 PR 合并后：#72 关闭留言（消费者 zoo-code-agent 的"重启续跑"解除阻塞）；#32 在办表同步
