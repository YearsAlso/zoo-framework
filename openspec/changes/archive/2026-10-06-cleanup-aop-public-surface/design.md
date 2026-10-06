# Design：清理 AOP 失效公共面

## D1 两段式弃用 `@worker` / `worker_register`

本变更把它们**移出全部公共 `__all__`**，但保留 `core/aop/worker.py` 模块一个 minor 周期：
`worker()` 返回的装饰器在被调用时发 `DeprecationWarning`（文案指明"注册进不被派发读取的
legacy 表，请改用 `Master.register_worker`"）。下个 minor 再物理删除模块与
`workers.WorkerRegister`。理由：从模块路径直接导入的使用者会得到**有声**的迁移信号，
而不是升级即 ImportError；符合仓库"装饰器契约/公共 API 变更需 CHANGELOG"的红线。

## D2 `register_worker` 装饰器整删，不修死分支

两条可选路径对比：修死分支 = 让它真接 `WorkerRegistry.register_class`，但那样它会与
`Master.register_worker` 形成**两条并行的注册真源**（一个是装饰器导入期副作用、一个是
运行期显式调用），正是 #29/#31 一路在消除的形态；且该装饰器全仓库零使用。整删后
`worker_registry.__all__` 同步收缩。`Master.register_worker` 方法（真实路径）不受影响。

## D3 `validation` 整模块删除

零使用、零规格、纯副作用全局（`params_validate_map` 无人读）。留着它的唯一效果是让
`__all__` 继续撒谎、让 #50 的载体清单继续虚长。若未来出现参数校验需求，先立规格再实现
（#51 的 aop 规格线），本变更不为其保留空壳。

## D4 拦截机制：导出白名单快照 + 逐项接通证据分置

"每项导出都可被有效使用"无法被一个通用测试机械验证（各装饰器语义不同）。落点拆两半：

- **白名单快照断言**：测试钉死三个 `__all__` 的精确集合——新增导出项必须先改白名单，
  评审时"这项接通了吗"变成必答问题；同时对 5 个已判废名做**负断言**（不得回流）
- **逐项接通证据**：由既有用例承担（`@params` 有 config-resolution 用例、`@event` 有
  event-dispatch 用例、`@configure` 有 Master 遍历 `config_funcs` 的行为用例、
  `Master.register_worker` 有 worker-scheduling 用例）；新判废项补弃用警告断言

## D5 示例修复取"可运行"路径

`demo_thread.py` 改用 `Master.register_worker(...)` 显式注册（与 templates 脚手架产出同
一路径），兑现 #49 验收里"示例要么可运行、要么如实标注"的前者；`example/main.py` 的
副作用导入注释改写为真实注册链。
