# 提案：fix-result-reactor-name-filter —— 结果筛选 MUST 按「注册名」匹配

## Why

issue #229 实锤：`WaiterResultReactor.worker_names` 是**永不匹配**的过滤器。

结果里的 `worker_name` 在结算时带上了实例序号后缀（注册名 `ok` → 结果 `ok_1`，见
`BaseWorker.name` = 注册名 + `_<num>`），而 `accepts` 做的是等值比较
`getattr(result, "worker_name", None) in self.worker_names`。于是按 docstring 承诺
（"set ``worker_names`` to receive results from only the named Workers"）设置
`worker_names = ["ok"]` 时，**所有**结果都被挡掉：无异常、无日志，静默不匹配。

框架自带的过滤入口实际不可用，调用方只能自己写 `startswith` 前缀匹配（过度放行——
`ok` 会连 `ok2` 的结果一起收下），或者把 `worker_names` 设成 `ok_1`
（但实例序号在声明筛选时不可预知，等于不可用）。在 zoo-code-agent 的批量任务派发里，
派发侧想只接收自己派出去的任务结果，一条都收不到。

## What Changes

- `WorkerResult` 增加**不带序号**的身份字段 `registry_name`（配置名，未配置时取类名），
  与带序号的 `worker_name` 并存——两者是同一 Worker 的两个身份，文档写明各自的用途。
- `WaiterResultReactor.accepts` 改为按**身份候选集**匹配：
  `registry_name`、`worker_name` 去掉尾部 `_<num>` 后的形态（兜住框架外自建的结果）、
  以及 `worker_name` 本身（精确实例名，兼容既有绕法）。
- 匹配保持**精确**，MUST NOT 退化成前缀匹配：以 `ok` 筛选 MUST NOT 收下 `ok2` 的结果。
- 类说明与 `accepts` docstring 写明筛选语义（注册名 + 精确实例名；空/None = 全收）。
- 新增回归用例 `tests/test_result_reactor_filter.py`。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `worker-scheduling`：修改 Requirement「Worker 结果 MUST 沿事件管道投递且可被按名过滤」
  ——结果 MUST 同时携带"带序号实例名"与"不带序号注册名"两个身份；筛选入口 SHALL 按注册名
  匹配并 SHALL 仍接受精确实例名；匹配 MUST 为精确匹配，MUST NOT 退化为前缀匹配。

## Impact

- **代码**：`zoo_framework/reactor/waiter_result_reactor.py`（`accepts` 匹配语义）、
  `zoo_framework/workers/worker_result.py`（`registry_name`）、
  `zoo_framework/workers/base_worker.py`（`registry_name` 属性并让 `name` 复用它）。
- **测试**：新增 `tests/test_result_reactor_filter.py`（8 条）。
- **兼容性**：`worker_names = ["ok_1"]`（既有绕法）仍被接受；`None` 仍表示全收；
  唯一行为变化是"按注册名筛选"从恒不匹配变为匹配，属修复方向。
- **已知限制**：注册名本身以 `_<数字>` 结尾时存在身份歧义（注册名 `ok_1` 的实例名
  `ok_1_1` 去后缀得 `ok_1`，与注册名 `ok` 的首个实例名同名）——该歧义源于"名字 + 序号"
  的既有命名方案，需以不冲突的注册名规避，本变更不引入新的规避机制。
