# example-hygiene 设计

## 决策记录

### 1. agent 子模块：选 b（保留 submodule + 文档说明），不内联

issue 给出二选一。选 b 的理由：

1. **内联与既定架构决议冲突**：把 `zoo-code-agent` 内联进主仓库实质上消除了"独立消费者
   仓库"这条验证线——它在仓外用自己的节奏跑框架 Agent 线的验证（memory 记录该项已定，
   "树内 submodule（已定，勿再议）；框架 Agent 线的验证消费方"）。
2. **体积收益为负**：内联增大主仓库体积却**不**带来"示例能跑"的收益——agent 是消费者
   项目，不是示例；普通访客本来就不需要克隆它。
3. **摩擦成本极低**：一条 `--recursive` 提示 + `example/README.md` 一段说明即可。
   主仓库的 clone 命令只在 README「Contributing」节与 CONTRIBUTING.md 出现，均下 strikes
   即修。

### 2. `demo_event.py` 的最小场景设计

现状只是 `@event("change_test_number")` 注册（可导入，无场景）。补场景 = 在
`__main__` 块里完成「构造 EventNode → 投递管道 → reactor 收到 → 打印」的最小闭环，
自包含、Ctrl-C 退出。不使用 `EventWorker` 内部细节，只走公开 API（`EventProvider` /
`event_channel` 链路的既有用法以 `@event` 装饰器 + 现有投递函数为准——实现时按现行
公开 API 编写，不自行造新接口）。

### 3. `example/minimal.py` = README 首屏示例的落盘版

README 的 30 秒示例（`Hello from MyWorker! Count: N`）已在 B 系列变更中实跑验证。
`minimal.py` 逐字沿用（只改模块说明注释），避免两处实现漂移。README 正文补一句
"该示例的完整落盘版在 `example/minimal.py`"。

### 4. `config.json` 只删 `_exports`，其余保留

`log` / `stateMachine` / `worker` 键都是 `ParamsPath` 真实解析的活跃键（示例演示
"带配置也能跑"的场景本身有价值）。只清死配置，不做无关整理（遵循外科手术式修改约束）。

### 5. 一致性测试不需要

doc-consistency-sweep 的机械测试（隐喻表、SVM 宣称、mockdocstrings、import 链）不涉及
example/ 的内容变更（example/*.py 的 import 是真实 `zoo_framework` API，不会被
`test_documented_imports_execute` 扫描——该测试只扫 docs/ 与 README 的代码块。
example/minimal.py 与 README 代码块逐字一致，天然同步，无需再加机械校验）。

## 风险与边界

- `master.register_worker` 与 `@event` 装饰器是 process-global 副作用——示例文件之间
  不会互相干扰（各自独立运行）。
- 本 change 不触碰 `zoo_framework/` 产品代码。
- 每个示例的期望输出写入 `example/README.md`；实跑验证全部留痕于 tasks.md。
